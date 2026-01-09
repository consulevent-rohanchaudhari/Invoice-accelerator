"""
Validation Engine Cloud Function
Applies business rules to validate invoices and detect exceptions
"""
import functions_framework
import os
import json
from datetime import datetime, timedelta
from decimal import Decimal


def load_validation_rules():
    """Load validation rules from config"""
    # TODO: Load from GCS or config file
    # For now, return hardcoded critical rules
    return {
        "required_fields": {
            "enabled": True,
            "fields": ["invoice_id", "supplier_name", "total_amount", "invoice_date"],
            "exception_type": "MISSING_REQUIRED_FIELDS",
            "severity": "high"
        },
        "amount_validation": {
            "enabled": True,
            "tolerance_percentage": 1.0
        },
        "tax_validation": {
            "enabled": True,
            "tolerance_percentage": 0.5
        },
        "date_validation": {
            "enabled": True,
            "max_days_old": 90
        }
    }


def validate_required_fields(invoice_data, rules):
    """Check if all required fields are present"""
    required_fields = rules["required_fields"]["fields"]
    missing_fields = []
    
    for field in required_fields:
        if field not in invoice_data or not invoice_data[field]:
            missing_fields.append(field)
    
    if missing_fields:
        return {
            "passed": False,
            "exception": {
                "type": rules["required_fields"]["exception_type"],
                "severity": rules["required_fields"]["severity"],
                "message": f"Missing required fields: {', '.join(missing_fields)}",
                "details": {"missing_fields": missing_fields}
            }
        }
    
    return {"passed": True}


def validate_amounts(invoice_data, rules):
    """Validate amount calculations"""
    exceptions = []
    
    total_amount = float(invoice_data.get("total_amount", 0))
    net_amount = float(invoice_data.get("net_amount", 0))
    tax_amount = float(invoice_data.get("total_tax_amount", 0))
    
    tolerance = rules["amount_validation"]["tolerance_percentage"] / 100
    
    # Check if total = net + tax (within tolerance)
    if net_amount > 0 and tax_amount > 0:
        expected_total = net_amount + tax_amount
        diff = abs(total_amount - expected_total)
        tolerance_amount = expected_total * tolerance
        
        if diff > tolerance_amount:
            exceptions.append({
                "type": "AMOUNT_MISMATCH",
                "severity": "high",
                "message": f"Total amount mismatch: expected {expected_total:.2f}, got {total_amount:.2f}",
                "details": {
                    "total_amount": total_amount,
                    "net_amount": net_amount,
                    "tax_amount": tax_amount,
                    "expected_total": expected_total,
                    "difference": diff
                }
            })
    
    # Check for negative amounts
    if total_amount < 0 or net_amount < 0 or tax_amount < 0:
        exceptions.append({
            "type": "NEGATIVE_AMOUNT",
            "severity": "high",
            "message": "Invoice contains negative amounts",
            "details": {
                "total_amount": total_amount,
                "net_amount": net_amount,
                "tax_amount": tax_amount
            }
        })
    
    # Check for large amounts (flag for review)
    if total_amount > 100000:
        exceptions.append({
            "type": "LARGE_AMOUNT",
            "severity": "medium",
            "message": f"Large invoice amount: ${total_amount:,.2f}",
            "details": {"total_amount": total_amount}
        })
    
    if exceptions:
        return {"passed": False, "exceptions": exceptions}
    
    return {"passed": True}


def validate_tax_calculation(invoice_data, rules):
    """Validate tax calculations"""
    net_amount = float(invoice_data.get("net_amount", 0))
    tax_amount = float(invoice_data.get("total_tax_amount", 0))
    
    if net_amount == 0 or tax_amount == 0:
        return {"passed": True}  # Skip if no tax
    
    # Calculate effective tax rate
    tax_rate = (tax_amount / net_amount) * 100
    
    # Common tax rates
    common_rates = [0, 5, 6, 7, 8, 8.25, 10]
    tolerance = rules["tax_validation"]["tolerance_percentage"]
    
    # Check if tax rate is close to a common rate
    is_valid = any(abs(tax_rate - rate) <= tolerance for rate in common_rates)
    
    if not is_valid:
        return {
            "passed": False,
            "exception": {
                "type": "UNUSUAL_TAX_RATE",
                "severity": "medium",
                "message": f"Unusual tax rate: {tax_rate:.2f}%",
                "details": {
                    "tax_rate": tax_rate,
                    "net_amount": net_amount,
                    "tax_amount": tax_amount
                }
            }
        }
    
    return {"passed": True}


def validate_dates(invoice_data, rules):
    """Validate invoice dates"""
    exceptions = []
    
    invoice_date_str = invoice_data.get("invoice_date")
    
    if not invoice_date_str:
        return {"passed": True}  # Skip if no date
    
    try:
        # Parse date (assume YYYY-MM-DD format)
        invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")
        today = datetime.now()
        
        # Check if invoice is in the future
        if invoice_date > today:
            exceptions.append({
                "type": "FUTURE_DATE",
                "severity": "high",
                "message": f"Invoice date is in the future: {invoice_date_str}",
                "details": {"invoice_date": invoice_date_str}
            })
        
        # Check if invoice is too old
        max_days = rules["date_validation"]["max_days_old"]
        age_days = (today - invoice_date).days
        
        if age_days > max_days:
            exceptions.append({
                "type": "OLD_INVOICE",
                "severity": "low",
                "message": f"Invoice is {age_days} days old (threshold: {max_days} days)",
                "details": {
                    "invoice_date": invoice_date_str,
                    "age_days": age_days
                }
            })
    
    except ValueError:
        exceptions.append({
            "type": "INVALID_DATE_FORMAT",
            "severity": "medium",
            "message": f"Invalid date format: {invoice_date_str}",
            "details": {"invoice_date": invoice_date_str}
        })
    
    if exceptions:
        return {"passed": False, "exceptions": exceptions}
    
    return {"passed": True}


@functions_framework.http
def validate_invoice(request):
    """
    Validate invoice against business rules
    
    Expected request:
    {
        "invoice_data": {
            "invoice_id": "INV-001",
            "supplier_name": "Acme Corp",
            "total_amount": 1500.00,
            "net_amount": 1400.00,
            "total_tax_amount": 100.00,
            "invoice_date": "2026-01-09",
            ...
        }
    }
    
    Returns:
    {
        "status": "success",
        "is_exception": false,
        "exceptions": [],
        "validation_results": {
            "required_fields": "passed",
            "amount_validation": "passed",
            ...
        }
    }
    """
    
    try:
        request_json = request.get_json()
        invoice_data = request_json.get("invoice_data")
        
        if not invoice_data:
            return {'error': 'invoice_data is required'}, 400
        
        print(f"Validating invoice: {invoice_data.get('invoice_id', 'unknown')}")
        
        # Load validation rules
        rules = load_validation_rules()
        
        # Run all validations
        all_exceptions = []
        validation_results = {}
        
        # 1. Required fields
        result = validate_required_fields(invoice_data, rules)
        validation_results["required_fields"] = "passed" if result["passed"] else "failed"
        if not result["passed"]:
            all_exceptions.append(result["exception"])
        
        # 2. Amount validation
        result = validate_amounts(invoice_data, rules)
        validation_results["amount_validation"] = "passed" if result["passed"] else "failed"
        if not result["passed"]:
            all_exceptions.extend(result.get("exceptions", []))
        
        # 3. Tax validation
        result = validate_tax_calculation(invoice_data, rules)
        validation_results["tax_validation"] = "passed" if result["passed"] else "failed"
        if not result["passed"]:
            all_exceptions.append(result["exception"])
        
        # 4. Date validation
        result = validate_dates(invoice_data, rules)
        validation_results["date_validation"] = "passed" if result["passed"] else "failed"
        if not result["passed"]:
            all_exceptions.extend(result.get("exceptions", []))
        
        # Determine if this is an exception
        is_exception = len(all_exceptions) > 0
        
        # Determine routing
        high_severity_exceptions = [e for e in all_exceptions if e["severity"] == "high"]
        requires_review = len(high_severity_exceptions) > 0
        
        return {
            "status": "success",
            "is_exception": is_exception,
            "requires_review": requires_review,
            "exceptions": all_exceptions,
            "exception_count": len(all_exceptions),
            "high_severity_count": len(high_severity_exceptions),
            "validation_results": validation_results,
            "invoice_id": invoice_data.get("invoice_id"),
            "total_amount": invoice_data.get("total_amount")
        }
        
    except Exception as e:
        print(f"Error in validation: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e)
        }, 500
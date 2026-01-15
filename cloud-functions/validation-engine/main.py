"""
Validation Engine Cloud Function
Applies business rules to validate invoices and detect exceptions
"""
import functions_framework
import os
import json
from datetime import datetime, timedelta
from decimal import Decimal


def validate_required_fields(invoice_data):
    """
    Check if required fields are present
    Exception Type: MISSING_REQUIRED_FIELDS
    """
    exceptions = []
    required_fields = ["invoice_id", "invoice_number", "supplier_name", "total_amount", "invoice_date"]
    missing_fields = []
    
    for field in required_fields:
        value = invoice_data.get(field)
        # FIX: Also check for None/null values
        if value is None or not value or value == "UNKNOWN" or value == "":
            missing_fields.append(field)
    
    if missing_fields:
        exceptions.append({
            "type": "MISSING_REQUIRED_FIELDS",
            "severity": "high",
            "message": f"Missing required fields: {', '.join(missing_fields)}",
            "details": {
                "missing_fields": missing_fields
            }
        })
    
    return exceptions


def validate_invoice_date(invoice_data):
    """
    Check if invoice date is valid (not in future)
    Exception Type: FUTURE_DATE
    """
    exceptions = []
    
    invoice_date_str = invoice_data.get("invoice_date")
    if not invoice_date_str:
        return exceptions
    
    try:
        # Parse date (handle MM/dd/yyyy format)
        if '/' in invoice_date_str:
            invoice_date = datetime.strptime(invoice_date_str, "%m/%d/%Y")
        elif '-' in invoice_date_str:
            invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")
        else:
            return exceptions
        
        today = datetime.now()
        days_old = (today - invoice_date).days
        

        
        # Check if invoice date is in the future
        if days_old < 0:
            exceptions.append({
                "type": "FUTURE_DATE",
                "severity": "high",
                "message": f"Invoice date is in the future: {invoice_date_str}",
                "details": {
                    "invoice_date": invoice_date_str
                }
            })
    
    except Exception as e:
        print(f"Error parsing invoice date: {str(e)}")
    
    return exceptions


def validate_amount_threshold(invoice_data):
    """
    Check if invoice amount is unusually high
    Exception Type: LARGE_AMOUNT
    """
    exceptions = []
    
    total_amount = float(invoice_data.get("total_amount", 0))
    threshold = 100000.00  # $100k threshold
    
    if total_amount > threshold:
        exceptions.append({
            "type": "LARGE_AMOUNT",
            "severity": "medium",
            "message": f"Invoice amount (${total_amount:,.2f}) exceeds review threshold (${threshold:,.2f})",
            "details": {
                "total_amount": total_amount,
                "threshold": threshold
            }
        })
    
    return exceptions


def validate_po_amount(invoice_data):
    """
    Check if invoice total amount exceeds PO amount
    Exception Type: EXCEEDS_PO_AMOUNT
    """
    exceptions = []
    
    invoice_total = float(invoice_data.get("total_amount", 0))
    po_amount = invoice_data.get("po_amount")  # Expected from external system
    
    if po_amount is not None:
        po_amount = float(po_amount)
        if invoice_total > po_amount:
            exceptions.append({
                "type": "EXCEEDS_PO_AMOUNT",
                "severity": "high",
                "message": f"Invoice amount (${invoice_total:,.2f}) exceeds PO amount (${po_amount:,.2f})",
                "details": {
                    "invoice_amount": invoice_total,
                    "po_amount": po_amount,
                    "difference": invoice_total - po_amount
                }
            })
    
    return exceptions


def validate_po_funds(invoice_data):
    """
    Check if PO has sufficient remaining funds
    Exception Type: INSUFFICIENT_PO_FUNDS
    """
    exceptions = []
    
    invoice_total = float(invoice_data.get("total_amount", 0))
    po_remaining_balance = invoice_data.get("po_remaining_balance")  # Expected from external system
    
    if po_remaining_balance is not None:
        po_remaining_balance = float(po_remaining_balance)
        if invoice_total > po_remaining_balance:
            exceptions.append({
                "type": "INSUFFICIENT_PO_FUNDS",
                "severity": "high",
                "message": f"Invoice amount (${invoice_total:,.2f}) exceeds PO remaining balance (${po_remaining_balance:,.2f})",
                "details": {
                    "invoice_amount": invoice_total,
                    "po_remaining_balance": po_remaining_balance,
                    "shortfall": invoice_total - po_remaining_balance
                }
            })
    
    return exceptions


def validate_po_receiving(invoice_data):
    """
    Check if PO receiving has happened
    Exception Type: PO_RECEIVING_NOT_COMPLETE
    """
    exceptions = []
    
    po_receiving_status = invoice_data.get("po_receiving_status")  # Expected from external system
    po_number = invoice_data.get("purchase_order_number")
    
    if po_number and po_receiving_status is not None:
        if po_receiving_status != "COMPLETE" and po_receiving_status != "RECEIVED":
            exceptions.append({
                "type": "PO_RECEIVING_NOT_COMPLETE",
                "severity": "high",
                "message": f"PO receiving not complete. Status: {po_receiving_status}",
                "details": {
                    "po_number": po_number,
                    "receiving_status": po_receiving_status
                }
            })
    
    return exceptions


def validate_tax_calculations(invoice_data):
    """
    Validate tax calculations are correct
    Exception Type: INCORRECT_TAX_CALCULATION
    """
    exceptions = []
    
    net_amount = float(invoice_data.get("net_amount", 0))
    tax_amount = float(invoice_data.get("total_tax_amount", 0))
    total_amount = float(invoice_data.get("total_amount", 0))
    
    # Only validate if we have the necessary amounts
    if net_amount > 0 and tax_amount >= 0:
        # Calculate expected total
        expected_total = net_amount + tax_amount
        
        # Allow small tolerance for rounding (0.01)
        tolerance = 0.01
        difference = abs(total_amount - expected_total)
        
        if difference > tolerance:
            exceptions.append({
                "type": "INCORRECT_TAX_CALCULATION",
                "severity": "high",
                "message": f"Tax calculation mismatch. Expected total: ${expected_total:,.2f}, Got: ${total_amount:,.2f}",
                "details": {
                    "net_amount": net_amount,
                    "tax_amount": tax_amount,
                    "expected_total": expected_total,
                    "actual_total": total_amount,
                    "difference": difference
                }
            })
    
    return exceptions


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
            "invoice_date": "01/15/2026",
            ...
        }
    }
    
    Returns:
    {
        "status": "success",
        "is_exception": false,
        "exceptions": []
    }
    """
    
    try:
        request_json = request.get_json()
        invoice_data = request_json.get("invoice_data")
        
        if not invoice_data:
            return {'error': 'invoice_data is required'}, 400
        
        print(f"Validating invoice: {invoice_data.get('invoice_id', 'unknown')}")
        
        # Run all validations
        all_exceptions = []
        validation_results = {}
        
        # NEW: Check required fields
        exceptions = validate_required_fields(invoice_data)
        validation_results["required_fields_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        # NEW: Check invoice date
        exceptions = validate_invoice_date(invoice_data)
        validation_results["invoice_date_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        # NEW: Check amount threshold
        exceptions = validate_amount_threshold(invoice_data)
        validation_results["amount_threshold_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        # Existing validations
        exceptions = validate_po_amount(invoice_data)
        validation_results["po_amount_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        exceptions = validate_po_funds(invoice_data)
        validation_results["po_funds_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        exceptions = validate_po_receiving(invoice_data)
        validation_results["po_receiving_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        exceptions = validate_tax_calculations(invoice_data)
        validation_results["tax_calculation_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        # Determine if this is an exception
        is_exception = len(all_exceptions) > 0
        requires_review = is_exception
        
        return {
            "status": "success",
            "is_exception": is_exception,
            "requires_review": requires_review,
            "exceptions": all_exceptions,
            "exception_count": len(all_exceptions),
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
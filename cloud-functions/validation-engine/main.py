"""
Validation Engine Cloud Function
Applies business rules to validate invoices and detect exceptions
Only checks for:
1. Invoice total amount > PO amount
2. Insufficient funds in PO
3. PO receiving didn't happen
4. Tax calculations not correct
"""
import functions_framework
import os
import json
from datetime import datetime
from decimal import Decimal


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
            "purchase_order_number": "PO-12345",
            "po_amount": 1600.00,  # Optional: from external system
            "po_remaining_balance": 500.00,  # Optional: from external system
            "po_receiving_status": "COMPLETE"  # Optional: from external system
            ...
        }
    }
    
    Returns:
    {
        "status": "success",
        "is_exception": false,
        "exceptions": [],
        "validation_results": {
            "po_amount_check": "passed",
            "po_funds_check": "passed",
            "po_receiving_check": "passed",
            "tax_calculation_check": "passed"
        }
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
        
        # 1. Check if invoice amount exceeds PO amount
        exceptions = validate_po_amount(invoice_data)
        validation_results["po_amount_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        # 2. Check if PO has sufficient funds
        exceptions = validate_po_funds(invoice_data)
        validation_results["po_funds_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        # 3. Check if PO receiving is complete
        exceptions = validate_po_receiving(invoice_data)
        validation_results["po_receiving_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        # 4. Check tax calculations
        exceptions = validate_tax_calculations(invoice_data)
        validation_results["tax_calculation_check"] = "passed" if len(exceptions) == 0 else "failed"
        all_exceptions.extend(exceptions)
        
        # Determine if this is an exception
        is_exception = len(all_exceptions) > 0
        
        # All exceptions are high severity
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

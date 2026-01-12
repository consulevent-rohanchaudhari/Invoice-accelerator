"""
Document AI Processor Cloud Function
Extracts structured data from PDFs using Document AI
"""
import functions_framework
import os
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
import json


def load_confidence_thresholds():
    """Load confidence thresholds from config"""
    return {
        "invoice_id": 0.95,
        "total_amount": 0.92,
        "supplier_name": 0.90,
        "invoice_date": 0.95,
        "net_amount": 0.90,
        "total_tax_amount": 0.88
    }


def process_document_ai(project_id, location, processor_id, gcs_uri):
    """
    Process document using Document AI
    
    Returns:
        dict with extracted entities and confidence scores
    """
    # Initialize Document AI client
    client = documentai.DocumentProcessorServiceClient()
    
    # Resource name
    name = client.processor_path(project_id, location, processor_id)
    
    # Read document from GCS
    storage_client = storage.Client()
    bucket_name = gcs_uri.replace('gs://', '').split('/')[0]
    blob_path = '/'.join(gcs_uri.replace('gs://', '').split('/')[1:])
    
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    document_content = blob.download_as_bytes()
    
    # Configure request
    raw_document = documentai.RawDocument(
        content=document_content,
        mime_type='application/pdf'
    )
    
    request = documentai.ProcessRequest(
        name=name,
        raw_document=raw_document
    )
    
    # Process document
    result = client.process_document(request=request)
    document = result.document
    
    # Extract entities with confidence scores
    extracted_data = {
        "entities": {},
        "confidence_scores": {},
        "raw_text": document.text
    }
    
    # Process entities - handle line_items specially
    line_items = []
    
    for entity in document.entities:
        entity_type = entity.type_
        entity_text = entity.mention_text
        confidence = entity.confidence
        
        # Special handling for line_item - collect all into array
        if entity_type == "line_item":
            # Extract line item details from properties if available
            line_item_data = {
                "raw_text": entity_text,
                "confidence": confidence
            }
            
            # Try to extract structured properties
            for prop in entity.properties:
                prop_type = prop.type_
                prop_value = prop.mention_text
                
                if prop_type in ["line_item/description", "description"]:
                    line_item_data["description"] = prop_value
                elif prop_type in ["line_item/quantity", "quantity"]:
                    try:
                        line_item_data["quantity"] = float(prop_value)
                    except:
                        line_item_data["quantity"] = prop_value
                elif prop_type in ["line_item/unit_price", "unit_price", "line_item/amount"]:
                    try:
                        line_item_data["unit_price"] = float(prop_value.replace('$', '').replace(',', ''))
                    except:
                        line_item_data["unit_price"] = prop_value
                elif prop_type in ["line_item/product_code", "product_code"]:
                    line_item_data["product_code"] = prop_value
            
            line_items.append(line_item_data)
        else:
            # For other entities, just store the value (overwrite is OK)
            extracted_data["entities"][entity_type] = entity_text
            extracted_data["confidence_scores"][entity_type] = confidence
    
    # Add collected line items as an array
    if line_items:
        extracted_data["entities"]["line_items"] = line_items
        # Use average confidence for line_items
        avg_confidence = sum(item.get("confidence", 0) for item in line_items) / len(line_items)
        extracted_data["confidence_scores"]["line_items"] = avg_confidence
    
    return extracted_data


@functions_framework.http
def process_with_document_ai(request):
    """
    Cloud Function to process documents with Document AI
    
    Expected request:
    {
        "gcs_uri": "gs://bucket/path/to/file.pdf",
        "document_type": "invoice"
    }
    
    Returns:
    {
        "status": "success",
        "extracted_data": {...},
        "confidence_scores": {...},
        "needs_synthesis": [list of fields below threshold]
    }
    """
    
    try:
        request_json = request.get_json()
        gcs_uri = request_json.get('gcs_uri')
        document_type = request_json.get('document_type', 'invoice')
        
        if not gcs_uri:
            return {'error': 'gcs_uri is required'}, 400
        
        print(f"Processing document: {gcs_uri}")
        
        # Get configuration
        project_id = os.getenv('GCP_PROJECT_ID')
        location = os.getenv('DOCUMENT_AI_LOCATION', 'us')
        processor_id = os.getenv('DOCUMENT_AI_PROCESSOR_ID')
        
        # Process document
        result = process_document_ai(project_id, location, processor_id, gcs_uri)
        
        print(f"Extracted {len(result['entities'])} entities")
        if 'line_items' in result['entities']:
            print(f"Found {len(result['entities']['line_items'])} line items")
        
        # Load confidence thresholds
        thresholds = load_confidence_thresholds()
        
        # Send ALL extracted fields to Gemini for comprehensive extraction
        needs_synthesis = []
        for field, value in result["entities"].items():
            if value is not None and str(value).strip():
                needs_synthesis.append({
                    "field": field,
                    "confidence": result["confidence_scores"].get(field, 0.95),
                    "threshold": thresholds.get(field, 0.95),
                    "current_value": value
                })
        
        return {
            "status": "success",
            "gcs_uri": gcs_uri,
            "extracted_data": result["entities"],
            "confidence_scores": result["confidence_scores"],
            "needs_synthesis": needs_synthesis,
            "raw_text_preview": result["raw_text"][:5000]  # Limit text preview
        }
        
    except Exception as e:
        print(f"Error in Document AI processing: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e)
        }, 500
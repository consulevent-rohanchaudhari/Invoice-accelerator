"""
Document AI Processor Cloud Function
Extracts structured data from PDFs using Document AI
"""
import functions_framework
import os
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
import json
import yaml


def load_confidence_thresholds():
    """Load confidence thresholds from config"""
    # For now, return hardcoded thresholds
    # TODO: Load from GCS or config file
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
        "raw_text": document.text[:1000]  # First 1000 chars for context
    }
    
    for entity in document.entities:
        entity_type = entity.type_
        entity_text = entity.mention_text
        confidence = entity.confidence
        
        extracted_data["entities"][entity_type] = entity_text
        extracted_data["confidence_scores"][entity_type] = confidence
    
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
        
        # Load confidence thresholds
        thresholds = load_confidence_thresholds()
        
        # Determine which fields need Gemini synthesis
        needs_synthesis = []
        for field, threshold in thresholds.items():
            score = result["confidence_scores"].get(field, 0.0)
            if score < threshold and score > 0:  # Only if field exists but low confidence
                needs_synthesis.append({
                    "field": field,
                    "confidence": score,
                    "threshold": threshold,
                    "current_value": result["entities"].get(field)
                })
        
        return {
            "status": "success",
            "gcs_uri": gcs_uri,
            "extracted_data": result["entities"],
            "confidence_scores": result["confidence_scores"],
            "needs_synthesis": needs_synthesis,
            "raw_text_preview": result["raw_text"]
        }
        
    except Exception as e:
        print(f"Error in Document AI processing: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e)
        }, 500
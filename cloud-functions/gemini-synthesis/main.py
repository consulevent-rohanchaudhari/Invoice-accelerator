"""
Gemini Synthesis Cloud Function
Uses comprehensive prompt for complete invoice extraction
"""
import functions_framework
import os
import json
import requests
import google.auth
from google.auth.transport.requests import Request
from google.cloud import storage
import base64


def get_access_token():
    """Get access token"""
    credentials, project = google.auth.default(
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    credentials.refresh(Request())
    return credentials.token


def load_extraction_prompt():
    """Load the comprehensive extraction prompt"""
    try:
        with open('INVOICE_EXTRACTION_PROMPT.md', 'r') as f:
            return f.read()
    except FileNotFoundError:
        print("Warning: INVOICE_EXTRACTION_PROMPT.md not found")
        # Return basic fallback prompt
        return """You are an expert invoice data extraction assistant. 
Extract all invoice fields accurately including invoice number, date, supplier, customer, amounts, and line items."""


def synthesize_with_gemini_comprehensive(pdf_uri, raw_text, existing_data):
    """Use Gemini with comprehensive prompt for full extraction"""
    project_id = os.getenv('GCP_PROJECT_ID')
    model_id = 'gemini-2.0-flash-exp'
    
    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
    
    token = get_access_token()
    
    # Get PDF from GCS if URI provided
    pdf_base64 = None
    if pdf_uri:
        try:
            storage_client = storage.Client()
            bucket_name = pdf_uri.replace('gs://', '').split('/')[0]
            blob_path = '/'.join(pdf_uri.replace('gs://', '').split('/')[1:])
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            pdf_bytes = blob.download_as_bytes()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            print("PDF loaded successfully")
        except Exception as e:
            print(f"Failed to load PDF: {e}")
    
    # Load comprehensive extraction prompt
    extraction_prompt = load_extraction_prompt()
    
    # Build full prompt
    full_prompt = f"""{extraction_prompt}

## DOCUMENT AI PRELIMINARY EXTRACTION (Reference)

Document AI provided the following preliminary extraction. Use this as a starting point, but re-extract and validate everything from the actual PDF document:
```json
{json.dumps(existing_data, indent=2)}
```

## RAW OCR TEXT (Additional Reference)
```
{raw_text[:4000] if raw_text else 'Not available'}
```

## YOUR TASK
1. Carefully review the PDF document provided
2. Extract ALL invoice fields according to the comprehensive schema above
3. Pay special attention to:
   - **Line items**: Extract EVERY line item in the invoice table with all details
   - **Amounts**: Remove currency symbols, ensure numeric values only
   - **Dates**: Convert to MM/dd/yyyy format
   - **Addresses**: Combine multi-line addresses into single formatted strings
   - **Missing fields**: If Document AI missed fields, extract them now
4. Return ONLY the JSON object with the exact field names from the schema
5. Do NOT include markdown code blocks, explanations, or any extra text

Output JSON:"""
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Build parts for the request
    parts = [{"text": full_prompt}]
    
    # Add PDF if available
    if pdf_base64:
        parts.append({
            "inline_data": {
                "mime_type": "application/pdf",
                "data": pdf_base64
            }
        })
    
    payload = {
        "contents": {
            "role": "user",
            "parts": parts
        },
        "generationConfig": {
            "temperature": 0.1,  # Low temperature for accuracy
            "maxOutputTokens": 8192,  # Allow for many line items
            "topP": 0.95
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    
    if response.status_code != 200:
        error_msg = f"Status {response.status_code}: {response.text}"
        print(f"Gemini API Error: {error_msg}")
        raise Exception(error_msg)
    
    result = response.json()
    
    # Extract text from response
    try:
        text_response = result['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError) as e:
        print(f"Unexpected response format: {result}")
        raise Exception(f"Failed to parse response: {e}")
    
    # Clean and parse JSON
    text_response = text_response.strip()
    if text_response.startswith('```json'):
        text_response = text_response[7:]
    if text_response.startswith('```'):
        text_response = text_response[3:]
    if text_response.endswith('```'):
        text_response = text_response[:-3]
    
    text_response = text_response.strip()
    
    try:
        extracted_data = json.loads(text_response)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON. First 500 chars: {text_response[:500]}")
        raise Exception(f"Invalid JSON from Gemini: {e}")
    
    return extracted_data


def synthesize_with_gemini_fields(raw_text, fields_to_improve, existing_data):
    """Legacy function: Use Gemini to improve specific fields (fallback)"""
    project_id = os.getenv('GCP_PROJECT_ID')
    model_id = 'gemini-2.5-flash'
    
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/global/publishers/google/models/{model_id}:generateContent"
    
    token = get_access_token()
    
    field_names = [f['field'] for f in fields_to_improve]
    
    prompt = f"""You are an expert invoice data extraction assistant. Extract and improve these fields: {', '.join(field_names)}

Invoice Text:
{raw_text[:8000]}

Current values:
{json.dumps(existing_data, indent=2)}

INSTRUCTIONS:
1. For line items: Parse into array of objects with description, quantity, unit_price, amount, product_code
2. For addresses: Combine multi-line into single formatted string
3. For dates: Convert to YYYY-MM-DD format
4. For amounts: Remove currency symbols, return numeric
5. Return SAME field names as requested

Return ONLY JSON:"""
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "contents": {
            "role": "user",
            "parts": {"text": prompt}
        },
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if response.status_code != 200:
        error_msg = f"Status {response.status_code}: {response.text}"
        print(f"Gemini API Error: {error_msg}")
        raise Exception(error_msg)
    
    result = response.json()
    text_response = result['candidates'][0]['content']['parts'][0]['text'].strip()
    
    # Clean JSON
    if text_response.startswith('```json'):
        text_response = text_response[7:]
    if text_response.startswith('```'):
        text_response = text_response[3:]
    if text_response.endswith('```'):
        text_response = text_response[:-3]
    
    improved_data = json.loads(text_response.strip())
    return improved_data


@functions_framework.http
def synthesize_fields(request):
    """Comprehensive extraction using Gemini with detailed prompt"""
    try:
        request_json = request.get_json()
        raw_text = request_json.get('raw_text', '')
        fields_to_improve = request_json.get('fields_to_improve', [])
        existing_data = request_json.get('existing_data', {})
        pdf_uri = request_json.get('gcs_uri', '')
        
        # Determine mode: comprehensive extraction or field-level improvement
        if pdf_uri and not fields_to_improve:
            # Comprehensive mode: re-extract everything from PDF
            print(f"Running comprehensive extraction for: {pdf_uri}")
            print(f"Document AI provided {len(existing_data)} fields")
            
            extracted_data = synthesize_with_gemini_comprehensive(pdf_uri, raw_text, existing_data)
            
            print(f"Comprehensive extraction complete")
            print(f"Extracted {len(extracted_data)} top-level fields")
            print(f"Line items: {len(extracted_data.get('line_items', []))}")
            
            return {
                "status": "success",
                "extracted_data": extracted_data,
                "mode": "comprehensive"
            }, 200
            
        elif fields_to_improve:
            # Field improvement mode: improve specific low-confidence fields
            print(f"Improving {len(fields_to_improve)} specific fields")
            
            improved_data = synthesize_with_gemini_fields(raw_text, fields_to_improve, existing_data)
            
            return {
                "status": "success",
                "improved_data": improved_data,
                "fields_improved": list(improved_data.keys()),
                "mode": "field_improvement"
            }, 200
            
        else:
            # No work to do
            return {
                "status": "success",
                "extracted_data": existing_data,
                "message": "No extraction or improvement needed"
            }, 200
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}, 500
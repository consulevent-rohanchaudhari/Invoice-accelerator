"""
Gemini Synthesis Cloud Function
Uses Gemini to improve low-confidence extractions
"""
import functions_framework
import os
import json
import requests
from google.auth import default
from google.auth.transport.requests import Request


def get_access_token():
    """Get access token for Vertex AI"""
    credentials, project = default()
    credentials.refresh(Request())
    return credentials.token


def synthesize_with_gemini(raw_text, fields_to_improve, existing_data):
    """
    Use Gemini to extract or improve specific fields via REST API
    """
    project_id = os.getenv('GCP_PROJECT_ID')
    location = os.getenv('GEMINI_LOCATION', 'us-central1')
    model = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
    
    # Get access token
    token = get_access_token()
    
    # Construct API endpoint
    url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model}:generateContent"
    
    # Create list of fields to improve
    field_names = [f['field'] for f in fields_to_improve]
    
    # Create prompt
    prompt = f"""You are an expert at extracting structured data from invoices and purchase orders.

Given the following document text, please extract the following fields with high accuracy:
{', '.join(field_names)}

Document Text:
{raw_text[:5000]}

Existing extracted data (may be incorrect or incomplete):
{json.dumps(existing_data, indent=2)}

Please provide ONLY a JSON object with the requested fields. Be precise with:
- Numbers: no currency symbols, use decimal notation (e.g., 1234.56)
- Dates: use YYYY-MM-DD format
- Text: exact as it appears in the document

JSON Response:
"""
    
    # Prepare request
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048
        }
    }
    
    # Make request
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    result = response.json()
    response_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
    
    # Parse JSON response (remove markdown code blocks if present)
    if response_text.startswith('```json'):
        response_text = response_text[7:]
    if response_text.startswith('```'):
        response_text = response_text[3:]
    if response_text.endswith('```'):
        response_text = response_text[:-3]
    
    improved_data = json.loads(response_text.strip())
    
    return improved_data


@functions_framework.http
def synthesize_fields(request):
    """
    Cloud Function to synthesize low-confidence fields using Gemini
    """
    
    try:
        request_json = request.get_json()
        raw_text = request_json.get('raw_text')
        fields_to_improve = request_json.get('fields_to_improve', [])
        existing_data = request_json.get('existing_data', {})
        
        if not raw_text:
            return {'error': 'raw_text is required'}, 400
        
        if not fields_to_improve:
            return {
                "status": "success",
                "improved_data": {},
                "message": "No fields to improve"
            }
        
        print(f"Synthesizing {len(fields_to_improve)} fields with Gemini")
        
        # Synthesize with Gemini
        improved_data = synthesize_with_gemini(raw_text, fields_to_improve, existing_data)
        
        return {
            "status": "success",
            "improved_data": improved_data,
            "fields_improved": list(improved_data.keys()),
            "fields_requested": [f['field'] for f in fields_to_improve]
        }
        
    except Exception as e:
        print(f"Error in Gemini synthesis: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e)
        }, 500
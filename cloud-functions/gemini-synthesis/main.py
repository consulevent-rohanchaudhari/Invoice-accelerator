"""
Gemini Synthesis Cloud Function
Uses Gemini 2.5 Flash for field improvement
"""
import functions_framework
import os
import json
import requests
import google.auth
from google.auth.transport.requests import Request


def get_access_token():
    """Get access token"""
    credentials, project = google.auth.default(
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    credentials.refresh(Request())
    return credentials.token


def synthesize_with_gemini(raw_text, fields_to_improve, existing_data):
    """Use Gemini to improve fields"""
    project_id = os.getenv('GCP_PROJECT_ID')
    model_id = 'gemini-2.5-flash'
    
    # Use global location as per documentation
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/global/publishers/google/models/{model_id}:generateContent"
    
    token = get_access_token()
    
    field_names = [f['field'] for f in fields_to_improve]
    
    prompt = f"""Extract these fields from the invoice: {', '.join(field_names)}

Invoice Text:
{raw_text[:3000]}

Current values:
{json.dumps(existing_data, indent=2)}

Return ONLY a JSON object with the fields. Format:
- Numbers: no symbols (e.g. 75.00)
- Dates: YYYY-MM-DD
- Text: exact from document

JSON:"""
    
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
    
    improved_data = json.loads(text_response.strip())
    return improved_data


@functions_framework.http
def synthesize_fields(request):
    """Synthesize low-confidence fields using Gemini"""
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
        
        print(f"Synthesizing {len(fields_to_improve)} fields")
        
        improved_data = synthesize_with_gemini(raw_text, fields_to_improve, existing_data)
        
        return {
            "status": "success",
            "improved_data": improved_data,
            "fields_improved": list(improved_data.keys())
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}, 500
"""
Email Processor Cloud Function
Fetches email details and attachments from Microsoft Graph API
"""
import functions_framework
import os
import base64
import json
from google.cloud import storage
from datetime import datetime
import requests


def get_access_token():
    """Get Microsoft Graph API access token"""
    tenant_id = os.getenv('AZURE_TENANT_ID')
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    data = {
        'client_id': client_id,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    
    response = requests.post(url, data=data)
    response.raise_for_status()
    
    return response.json()['access_token']


def get_email_details(access_token, user_email, message_id):
    """Fetch email details including attachments"""
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    params = {'$expand': 'attachments'}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    return response.json()


def validate_pdf(filename):
    """Check if file is a PDF"""
    return filename.lower().endswith('.pdf')


def upload_to_gcs(bucket_name, blob_path, content, content_type, metadata=None):
    """Upload file to Google Cloud Storage"""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    blob.upload_from_string(content, content_type=content_type)
    
    if metadata:
        blob.metadata = metadata
        blob.patch()
    
    return f"gs://{bucket_name}/{blob_path}"


@functions_framework.http
def process_email(request):
    """
    Process email and extract attachments
    
    Expected request body:
    {
        "message_id": "AAMkAD...",
        "user_email": "rohan.chaudhari@consuleventinc.com"
    }
    """
    
    try:
        request_json = request.get_json()
        message_id = request_json.get('message_id')
        user_email = request_json.get('user_email', os.getenv('SENDER_EMAIL'))
        
        if not message_id:
            return {'error': 'message_id is required'}, 400
        
        print(f"Processing email: {message_id}")
        
        access_token = get_access_token()
        email_data = get_email_details(access_token, user_email, message_id)
        
        sender = email_data.get('from', {}).get('emailAddress', {}).get('address', 'unknown')
        subject = email_data.get('subject', 'No Subject')
        received_time = email_data.get('receivedDateTime')
        
        attachments = email_data.get('attachments', [])
        processed_files = []
        rejected_files = []
        
        raw_bucket = os.getenv('GCS_BUCKET_RAW')
        rejected_bucket = os.getenv('GCS_BUCKET_REJECTED')
        
        for attachment in attachments:
            filename = attachment.get('name')
            content_bytes = base64.b64decode(attachment.get('contentBytes', ''))
            
            if not validate_pdf(filename):
                rejected_files.append({
                    "filename": filename,
                    "reason": "Invalid file format. Only PDF files are accepted."
                })
                
                blob_path = f"{message_id}/{datetime.utcnow().isoformat()}/{filename}"
                upload_to_gcs(
                    rejected_bucket,
                    blob_path,
                    content_bytes,
                    'application/octet-stream',
                    metadata={
                        'message_id': message_id,
                        'sender': sender,
                        'received_time': received_time
                    }
                )
                continue
            
            blob_path = f"{message_id}/{datetime.utcnow().isoformat()}/{filename}"
            gcs_uri = upload_to_gcs(
                raw_bucket,
                blob_path,
                content_bytes,
                'application/pdf',
                metadata={
                    'message_id': message_id,
                    'sender': sender,
                    'subject': subject,
                    'received_time': received_time,
                    'original_filename': filename
                }
            )
            
            processed_files.append({
                "filename": filename,
                "gcs_uri": gcs_uri,
                "size_bytes": len(content_bytes)
            })
        
        return {
            "status": "success",
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "processed_files": processed_files,
            "rejected_files": rejected_files
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}, 500
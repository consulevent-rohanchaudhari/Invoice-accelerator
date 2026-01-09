"""
Webhook Receiver Cloud Function
Receives notifications from Microsoft Graph API when new emails arrive
"""
import functions_framework
import os
import json
import hmac
import hashlib
from google.cloud import workflows_v1
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1 import Execution


def verify_webhook_signature(request):
    """
    Verify that the webhook request is from Microsoft
    """
    # Get the signature from headers
    signature = request.headers.get('X-Microsoft-Signature')
    
    if not signature:
        return False
    
    # Get the webhook secret
    secret = os.getenv('OUTLOOK_WEBHOOK_SECRET').encode('utf-8')
    
    # Calculate expected signature
    body = request.get_data()
    expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(signature, expected_signature)


def trigger_workflow(email_data):
    """
    Trigger Cloud Workflow to process the email
    """
    project_id = os.getenv('GCP_PROJECT_ID')
    location = os.getenv('GCP_REGION')
    workflow_id = 'invoice-processing-workflow'
    
    # Create workflow execution client
    execution_client = executions_v1.ExecutionsClient()
    
    # Construct the fully qualified workflow path
    workflow_path = f"projects/{project_id}/locations/{location}/workflows/{workflow_id}"
    
    # Create execution request
    execution = Execution(argument=json.dumps(email_data))
    
    request = executions_v1.CreateExecutionRequest(
        parent=workflow_path,
        execution=execution
    )
    
    # Execute workflow
    response = execution_client.create_execution(request=request)
    
    return response.name


@functions_framework.http
def webhook_receiver(request):
    """
    Main webhook receiver function
    
    Handles two types of requests:
    1. Validation request - Microsoft verifies the endpoint
    2. Notification request - New email notification
    """
    
    # Handle validation request (initial setup)
    if request.method == 'GET':
        validation_token = request.args.get('validationToken')
        if validation_token:
            # Return validation token in plain text
            return validation_token, 200, {'Content-Type': 'text/plain'}
    
    # Handle notification request
    if request.method == 'POST':
        try:
            # Verify webhook signature (optional but recommended)
            # Uncomment when you set up signature validation in Microsoft Graph
            # if not verify_webhook_signature(request):
            #     return {'error': 'Invalid signature'}, 401
            
            # Parse the notification
            notification_data = request.get_json()
            
            print(f"Received notification: {json.dumps(notification_data)}")
            
            # Microsoft Graph sends notifications in this format:
            # {
            #   "value": [
            #     {
            #       "subscriptionId": "...",
            #       "changeType": "created",
            #       "resource": "Users/{user-id}/Messages/{message-id}",
            #       "resourceData": {...}
            #     }
            #   ]
            # }
            
            if 'value' in notification_data:
                for notification in notification_data['value']:
                    # Extract email details
                    change_type = notification.get('changeType')
                    resource = notification.get('resource')
                    
                    # Only process new emails
                    if change_type == 'created' and 'Messages' in resource:
                        # Extract message ID from resource path
                        # Format: Users/{user-id}/Messages/{message-id}
                        message_id = resource.split('/')[-1]
                        
                        # Prepare data for workflow
                        email_data = {
                            'message_id': message_id,
                            'resource': resource,
                            'change_type': change_type,
                            'subscription_id': notification.get('subscriptionId')
                        }
                        
                        # Trigger workflow
                        execution_name = trigger_workflow(email_data)
                        print(f"Triggered workflow: {execution_name}")
            
            # Always return 202 Accepted to Microsoft
            return {'status': 'accepted'}, 202
            
        except Exception as e:
            print(f"Error processing webhook: {str(e)}")
            # Still return 202 to avoid Microsoft retrying
            return {'status': 'error', 'message': str(e)}, 202
    
    return {'error': 'Method not allowed'}, 405
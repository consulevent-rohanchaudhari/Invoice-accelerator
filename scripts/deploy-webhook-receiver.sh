#!/bin/bash

# Deploy webhook receiver Cloud Function

PROJECT_ID="consulevent-ap-invoice"
REGION="us-central1"
FUNCTION_NAME="invoice-webhook-receiver"

echo "Deploying webhook receiver Cloud Function..."

gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=cloud-functions/webhook-receiver \
  --entry-point=webhook_receiver \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION \
  --set-env-vars OUTLOOK_WEBHOOK_SECRET=Sak7OrnGVWJkrTVE5rmZm9GRZwGK4Ei2SrypTCrdAGA=

echo "Deployment complete!"
echo "Function URL will be displayed above - copy it for webhook setup"
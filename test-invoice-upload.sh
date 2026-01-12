#!/bin/bash

# Test Invoice Upload & Processing Script - End to End (Skips Email Step)
# This script uploads a file and processes it directly through Cloud Functions
# Usage: ./test-invoice-upload.sh invoice.pdf

# Start total timer
TOTAL_START_TIME=$(date +%s)

if [ -z "$1" ]; then
    echo "Usage: ./test-invoice-upload.sh /path/to/invoice.pdf"
    echo "Example: ./test-invoice-upload.sh invoice2.pdf"
    exit 1
fi

PDF_PATH="$1"

if [ ! -f "$PDF_PATH" ]; then
    echo "Error: File not found: $PDF_PATH"
    exit 1
fi

# Configuration
PROJECT_ID="consulevent-ap-invoice"
DATASET_ID="invoice_processing"
BUCKET="consulevent-invoices-raw"
REGION="us-central1"
TIMESTAMP=$(date +%s)
FILENAME=$(basename "$PDF_PATH")
MESSAGE_ID="test-${TIMESTAMP}"

# Determine Python command (use backend venv if available)
if [ -f "backend/venv/bin/python" ]; then
    PYTHON_CMD="backend/venv/bin/python"
elif [ -d "backend/venv" ] && [ -f "backend/venv/bin/python3" ]; then
    PYTHON_CMD="backend/venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# Create proper folder structure: message_id/timestamp/filename
BLOB_PATH="${MESSAGE_ID}/$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)/${FILENAME}"
GCS_URI="gs://${BUCKET}/${BLOB_PATH}"

echo "🚀 Starting End-to-End Invoice Processing (Skipping Email Step)"
echo "================================================================"
echo ""

# Step 1: Upload to GCS
echo "📤 Step 1: Uploading invoice to GCS..."
echo "   File: ${FILENAME}"
echo "   Bucket: ${BUCKET}"
echo "   Path: ${BLOB_PATH}"
echo "   GCS URI: ${GCS_URI}"

# Use gcloud storage instead of gsutil (better credential handling)
echo "   Uploading..."

# Try to refresh credentials first
gcloud auth application-default print-access-token > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "   ⚠️  Credentials need refresh. Please run:"
    echo "      gcloud auth application-default login"
    echo ""
    read -p "   Do you want to refresh credentials now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud auth application-default login
    else
        echo "❌ Cannot proceed without valid credentials"
        exit 1
    fi
fi

# Upload without --quiet to allow credential refresh if needed
gcloud storage cp "$PDF_PATH" "gs://${BUCKET}/${BLOB_PATH}"

if [ $? -ne 0 ]; then
    echo "❌ Failed to upload file to GCS"
    echo ""
    echo "💡 Troubleshooting:"
    echo "   1. Refresh credentials: gcloud auth application-default login"
    echo "   2. Check bucket exists: gcloud storage ls gs://${BUCKET}"
    echo "   3. Verify permissions: gcloud projects get-iam-policy ${PROJECT_ID}"
    exit 1
fi

echo "✅ Upload complete!"
echo ""

# Step 2: Document AI Processing
echo "📄 Step 2: Extracting data with Document AI..."
echo "   Calling Cloud Function: invoice-document-ai-processor"

# Use gcloud functions call which handles OIDC authentication automatically
# This is necessary because Cloud Functions require OIDC authentication
DOC_AI_RAW=$(gcloud functions call invoice-document-ai-processor \
    --region=${REGION} \
    --data "{\"gcs_uri\":\"${GCS_URI}\",\"document_type\":\"invoice\"}" \
    2>&1)

# Extract JSON from response (gcloud may output other text)
DOC_AI_RESPONSE=$(echo "$DOC_AI_RAW" | grep -o '{.*}' | jq -c '.' 2>/dev/null || echo "$DOC_AI_RAW")

if echo "$DOC_AI_RESPONSE" | jq -e '.status == "success" or .extracted_data != null' >/dev/null 2>&1; then
    echo "✅ Document AI extraction completed!"
    # Extract only the extracted_data part and ensure it's valid JSON
    EXTRACTED_DATA=$(echo "$DOC_AI_RESPONSE" | jq -c '.extracted_data // {}' 2>/dev/null)
    NEEDS_SYNTHESIS=$(echo "$DOC_AI_RESPONSE" | jq -c '.needs_synthesis // []' 2>/dev/null)
    RAW_TEXT_PREVIEW=$(echo "$DOC_AI_RESPONSE" | jq -r '.raw_text_preview // ""' 2>/dev/null)
    
    if [ -z "$EXTRACTED_DATA" ] || [ "$EXTRACTED_DATA" = "null" ]; then
        echo "⚠️  Warning: No extracted_data found, using empty object"
        EXTRACTED_DATA="{}"
    fi
    # Validate JSON
    if ! echo "$EXTRACTED_DATA" | jq . >/dev/null 2>&1; then
        echo "❌ Invalid JSON in extracted_data"
        echo "Response: $DOC_AI_RESPONSE"
        exit 1
    fi
else
    echo "❌ Document AI extraction failed"
    echo "$DOC_AI_RAW"
    echo "💡 Check logs: gcloud functions logs read invoice-document-ai-processor --limit 10"
    exit 1
fi

# Step 2.5: Gemini Enhancement (ALWAYS - validates and completes Document AI extraction)
STEP_START=$(date +%s)
echo ""
echo "🤖 Step 2.5: Enhancing extraction with Gemini (validates + completes)..."
echo "   Document AI extracted: $(echo "$EXTRACTED_DATA" | jq 'keys | length') fields"

# Build payload for comprehensive mode (with gcs_uri for PDF access)
GEMINI_PAYLOAD=$(jq -n \
    --arg gcs_uri "$GCS_URI" \
    --arg raw_text "$RAW_TEXT_PREVIEW" \
    --argjson existing_data "$EXTRACTED_DATA" \
    '{
        "gcs_uri": $gcs_uri,
        "raw_text": $raw_text,
        "existing_data": $existing_data
    }')

# Use gcloud functions call which handles OIDC authentication automatically
GEMINI_RAW=$(gcloud functions call gemini-synthesis \
    --region=${REGION} \
    --data "$GEMINI_PAYLOAD" \
    2>&1)

# Extract JSON from response
GEMINI_RESPONSE=$(echo "$GEMINI_RAW" | grep -o '{.*}' | jq -c '.' 2>/dev/null || echo "$GEMINI_RAW")

STEP_END=$(date +%s)
STEP_DURATION=$((STEP_END - STEP_START))

if echo "$GEMINI_RESPONSE" | jq -e '.status == "success" and .extracted_data != null' >/dev/null 2>&1; then
    echo "✅ Gemini enhancement completed! (⏱️  ${STEP_DURATION}s)"
    
    # Get Gemini's enhanced extraction
    GEMINI_DATA=$(echo "$GEMINI_RESPONSE" | jq -c '.extracted_data // {}' 2>/dev/null)
    
    if [ -n "$GEMINI_DATA" ] && [ "$GEMINI_DATA" != "null" ] && [ "$GEMINI_DATA" != "{}" ]; then
        # Compare what changed
        DOC_AI_FIELDS=$(echo "$EXTRACTED_DATA" | jq 'keys | length' 2>/dev/null || echo "0")
        GEMINI_FIELDS=$(echo "$GEMINI_DATA" | jq 'keys | length' 2>/dev/null || echo "0")
        LINE_ITEM_COUNT=$(echo "$GEMINI_DATA" | jq '.line_items | length' 2>/dev/null || echo "0")
        
        # Use Gemini's enhanced data as final result
        EXTRACTED_DATA="$GEMINI_DATA"
        
        echo "   📊 Document AI: ${DOC_AI_FIELDS} fields"
        echo "   ✨ Gemini enhanced to: ${GEMINI_FIELDS} fields"
        echo "   📋 Line items extracted: ${LINE_ITEM_COUNT}"
    else
        echo "   ⚠️  Warning: Gemini returned empty data, keeping Document AI extraction"
    fi
else
    echo "⚠️  Warning: Gemini enhancement failed (⏱️  ${STEP_DURATION}s)"
    echo "   Falling back to Document AI extraction only"
    if [ -n "$GEMINI_RESPONSE" ]; then
        echo "   Response: $(echo "$GEMINI_RESPONSE" | head -c 200)..."
    fi
fi

echo ""

# Step 3: Validation
echo "✅ Step 3: Validating invoice..."
echo "   Calling Cloud Function: invoice-validation-engine"

# Use gcloud functions call which handles OIDC authentication automatically
VALIDATION_RAW=$(gcloud functions call invoice-validation-engine \
    --region=${REGION} \
    --data "{\"invoice_data\":${EXTRACTED_DATA}}" \
    2>&1)

# Extract JSON from response (gcloud may output other text)
VALIDATION_RESPONSE=$(echo "$VALIDATION_RAW" | grep -o '{.*}' | jq -c '.' 2>/dev/null || echo "$VALIDATION_RAW")

# Debug: Print validation response
echo "   Debug: Validation response:"
echo "$VALIDATION_RESPONSE" | jq . 2>/dev/null || echo "$VALIDATION_RESPONSE"

# Validate JSON and extract is_exception
if echo "$VALIDATION_RESPONSE" | jq . >/dev/null 2>&1; then
    IS_EXCEPTION=$(echo "$VALIDATION_RESPONSE" | jq -r '.is_exception // false' 2>/dev/null || echo "false")
    EXCEPTION_COUNT=$(echo "$VALIDATION_RESPONSE" | jq -r '.exception_count // 0' 2>/dev/null || echo "0")
    echo "   Debug: is_exception=${IS_EXCEPTION}, exception_count=${EXCEPTION_COUNT}"
else
    echo "⚠️  Warning: Could not parse validation response as JSON"
    IS_EXCEPTION="false"
fi

if echo "$VALIDATION_RESPONSE" | grep -q '"status":"success"'; then
    echo "✅ Validation completed!"
    if [ "$IS_EXCEPTION" = "true" ]; then
        echo "   ⚠️  Invoice has exceptions - will write to exceptions table"
    else
        echo "   ✅ Invoice passed validation - will write to invoices_processed table"
    fi
else
    echo "⚠️  Validation response unclear, but continuing..."
fi

echo ""

# Step 4: Write to BigQuery directly (like the Cloud Workflow does)
echo "📊 Step 4: Writing to BigQuery..."

# Extract data from responses
INVOICE_ID=$(echo "$EXTRACTED_DATA" | jq -r '.invoice_number // .invoice_id // "UNKNOWN"')
SUPPLIER_NAME=$(echo "$EXTRACTED_DATA" | jq -r '.supplier_name // null' 2>/dev/null || echo "null")
INVOICE_DATE=$(echo "$EXTRACTED_DATA" | jq -r '.invoice_date // null' 2>/dev/null || echo "null")
TOTAL_AMOUNT=$(echo "$EXTRACTED_DATA" | jq -r '.total_amount // null' 2>/dev/null || echo "null")
NET_AMOUNT=$(echo "$EXTRACTED_DATA" | jq -r '.net_amount // null' 2>/dev/null || echo "null")
TOTAL_TAX=$(echo "$EXTRACTED_DATA" | jq -r '.total_tax_amount // null' 2>/dev/null || echo "null")
CURRENCY=$(echo "$EXTRACTED_DATA" | jq -r '.currency // null' 2>/dev/null || echo "null")

# Prepare JSON data for BigQuery insert (using insertAll like Cloud Workflow)
if [ "$IS_EXCEPTION" = "true" ]; then
    # Write to exceptions table using bq insert (matches Cloud Workflow insertAll)
    EXCEPTION_ID="${MESSAGE_ID}-${FILENAME}"
    EXCEPTION_TYPE=$(echo "$VALIDATION_RESPONSE" | jq -r '.exceptions[0].type // "VALIDATION_ERROR"' 2>/dev/null || echo "VALIDATION_ERROR")
    EXCEPTION_SEVERITY=$(echo "$VALIDATION_RESPONSE" | jq -r '.exceptions[0].severity // "medium"' 2>/dev/null || echo "medium")
    ALL_EXCEPTIONS=$(echo "$VALIDATION_RESPONSE" | jq -c '.exceptions // []' 2>/dev/null || echo "[]")
    
    # Validate JSON values before using --argjson
    if ! echo "$ALL_EXCEPTIONS" | jq . >/dev/null 2>&1; then
        echo "⚠️  Warning: Invalid JSON in all_exceptions, using empty array"
        ALL_EXCEPTIONS="[]"
    fi
    
    if ! echo "$EXTRACTED_DATA" | jq . >/dev/null 2>&1; then
        echo "❌ Error: Invalid JSON in extracted_data"
        exit 1
    fi
    
    echo "   Writing to exceptions table..."
    
    # Get current date for received_date (matching Cloud Workflow format)
    RECEIVED_DATE=$(date +%Y-%m-%d)
    
    # Create JSON row for insertAll (matching Cloud Workflow format)
    JSON_ROW=$(jq -n \
        --arg exception_id "$EXCEPTION_ID" \
        --arg invoice_id "$INVOICE_ID" \
        --arg message_id "$MESSAGE_ID" \
        --arg filename "$FILENAME" \
        --arg gcs_uri "$GCS_URI" \
        --arg supplier_name "${SUPPLIER_NAME}" \
        --arg exception_type "$EXCEPTION_TYPE" \
        --arg exception_severity "$EXCEPTION_SEVERITY" \
        --argjson all_exceptions "$ALL_EXCEPTIONS" \
        --argjson extracted_data "$EXTRACTED_DATA" \
        --arg total_amount "${TOTAL_AMOUNT}" \
        --arg invoice_date "${INVOICE_DATE}" \
        --arg received_date "$RECEIVED_DATE" \
        '{
            "exception_id": $exception_id,
            "invoice_id": $invoice_id,
            "message_id": $message_id,
            "filename": $filename,
            "gcs_uri": $gcs_uri,
            "supplier_name": (if $supplier_name != "null" then $supplier_name else null end),
            "total_amount": (if $total_amount != "null" and $total_amount != "" then ($total_amount | tonumber) else null end),
            "invoice_date": (if $invoice_date != "null" and $invoice_date != "" then $invoice_date else null end),
            "exception_type": $exception_type,
            "exception_severity": $exception_severity,
            "all_exceptions": $all_exceptions,
            "status": "PENDING",
            "received_date": $received_date,
            "raw_extracted_data": $extracted_data
        }')
    
    # Debug: Print JSON being inserted
    echo "   Debug: JSON row to insert:"
    echo "$JSON_ROW" | jq . | head -20
    
    # Write to BigQuery using bq query with INSERT (like backend does)
    echo "   Executing BigQuery INSERT..."
    
    # Escape single quotes in JSON strings for SQL
    EXCEPTION_ID_ESCAPED=$(echo "$EXCEPTION_ID" | sed "s/'/''/g")
    INVOICE_ID_ESCAPED=$(echo "$INVOICE_ID" | sed "s/'/''/g")
    MESSAGE_ID_ESCAPED=$(echo "$MESSAGE_ID" | sed "s/'/''/g")
    FILENAME_ESCAPED=$(echo "$FILENAME" | sed "s/'/''/g")
    GCS_URI_ESCAPED=$(echo "$GCS_URI" | sed "s/'/''/g")
    SUPPLIER_NAME_ESCAPED=$(echo "${SUPPLIER_NAME}" | sed "s/'/''/g")
    EXCEPTION_TYPE_ESCAPED=$(echo "$EXCEPTION_TYPE" | sed "s/'/''/g")
    EXCEPTION_SEVERITY_ESCAPED=$(echo "$EXCEPTION_SEVERITY" | sed "s/'/''/g")
    
    # Build SQL INSERT query (matching backend format)
    # For exceptions: invoice_date should be NULL if format is invalid
    # The exception details in all_exceptions will explain what's wrong
    # Don't try to "fix" invalid dates - that defeats the purpose of the exception
    INVOICE_DATE_SQL="NULL"
    if [ "$INVOICE_DATE" != "null" ] && [ -n "$INVOICE_DATE" ]; then
        # Only accept valid YYYY-MM-DD format, otherwise NULL
        if echo "$INVOICE_DATE" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
            INVOICE_DATE_SQL="CAST('${INVOICE_DATE}' AS DATE)"
        else
            # Invalid format - leave as NULL (exception explains why)
            INVOICE_DATE_SQL="NULL"
        fi
    fi
    
    SUPPLIER_NAME_SQL="NULL"
    [ "$SUPPLIER_NAME" != "null" ] && [ -n "$SUPPLIER_NAME" ] && SUPPLIER_NAME_SQL="'${SUPPLIER_NAME_ESCAPED}'"
    
    TOTAL_AMOUNT_SQL="NULL"
    [ "$TOTAL_AMOUNT" != "null" ] && [ -n "$TOTAL_AMOUNT" ] && TOTAL_AMOUNT_SQL="${TOTAL_AMOUNT}"
    
    # Escape JSON for SQL - use jq to properly escape control characters like newlines
    EXTRACTED_DATA_SQL=$(echo "$EXTRACTED_DATA" | jq -c . 2>/dev/null | sed "s/'/''/g")
    if [ -z "$EXTRACTED_DATA_SQL" ]; then
        echo "❌ Error: Failed to escape JSON for SQL"
        exit 1
    fi
    
    BQ_OUTPUT=$(bq query --use_legacy_sql=false --format=none <<EOF
INSERT INTO \`${PROJECT_ID}.${DATASET_ID}.exceptions\`
(exception_id, invoice_id, message_id, filename, gcs_uri, received_date, invoice_date, supplier_name, total_amount, exception_type, exception_severity, all_exceptions, status, raw_extracted_data)
VALUES
('${EXCEPTION_ID_ESCAPED}', '${INVOICE_ID_ESCAPED}', '${MESSAGE_ID_ESCAPED}', '${FILENAME_ESCAPED}', '${GCS_URI_ESCAPED}', CURRENT_DATE(), ${INVOICE_DATE_SQL}, ${SUPPLIER_NAME_SQL}, ${TOTAL_AMOUNT_SQL}, '${EXCEPTION_TYPE_ESCAPED}', '${EXCEPTION_SEVERITY_ESCAPED}', JSON '${ALL_EXCEPTIONS}', 'PENDING', JSON '${EXTRACTED_DATA_SQL}')
EOF
    2>&1)
    BQ_EXIT_CODE=$?
    
    if [ $BQ_EXIT_CODE -eq 0 ]; then
        echo "✅ Data written to BigQuery (exceptions table)!"
        TABLE_NAME="exceptions"
    else
        echo "❌ Failed to write to BigQuery exceptions table (exit code: $BQ_EXIT_CODE)"
        echo "Error output: $BQ_OUTPUT"
        echo ""
        echo "💡 Check BigQuery permissions and table schema"
        echo "   Try: bq show ${PROJECT_ID}:${DATASET_ID}.exceptions"
        exit 1
    fi
else
    # Write to invoices_processed table using bq insert (matches Cloud Workflow insertAll)
    echo "   Writing to invoices_processed table..."
    
    # Prepare data for Python script (using parameterized queries like backend)
    PYTHON_DATA=$(jq -n \
        --arg invoice_id "$INVOICE_ID" \
        --arg message_id "$MESSAGE_ID" \
        --arg filename "$FILENAME" \
        --arg gcs_uri "$GCS_URI" \
        --arg supplier_name "${SUPPLIER_NAME}" \
        --argjson extracted_data "$EXTRACTED_DATA" \
        --arg total_amount "${TOTAL_AMOUNT}" \
        --arg net_amount "${NET_AMOUNT}" \
        --arg total_tax "${TOTAL_TAX}" \
        --arg currency "${CURRENCY}" \
        --arg invoice_date "${INVOICE_DATE}" \
        '{
            "invoice_id": $invoice_id,
            "message_id": $message_id,
            "filename": $filename,
            "gcs_uri": $gcs_uri,
            "supplier_name": (if $supplier_name != "null" then $supplier_name else null end),
            "total_amount": (if $total_amount != "null" and $total_amount != "" then ($total_amount | tonumber) else null end),
            "net_amount": (if $net_amount != "null" and $net_amount != "" then ($net_amount | tonumber) else null end),
            "total_tax_amount": (if $total_tax != "null" and $total_tax != "" then ($total_tax | tonumber) else null end),
            "currency": (if $currency != "null" and $currency != "" then $currency else null end),
            "invoice_date": (if $invoice_date != "null" and $invoice_date != "" then $invoice_date else null end),
            "raw_extracted_data": $extracted_data
        }')
    
    # Use Python script with parameterized queries (like backend) to handle JSON properly
    echo "   Executing BigQuery INSERT using Python script..."
    PYTHON_OUTPUT=$($PYTHON_CMD scripts/write-to-bq.py "invoices_processed" "$PYTHON_DATA" 2>&1)
    PYTHON_EXIT_CODE=$?
    
    if [ $PYTHON_EXIT_CODE -eq 0 ] && echo "$PYTHON_OUTPUT" | grep -q "SUCCESS"; then
        echo "✅ Data written to BigQuery (invoices_processed table)!"
        TABLE_NAME="invoices_processed"
    else
        echo "❌ Failed to write to BigQuery invoices_processed table"
        echo "Error output: $PYTHON_OUTPUT"
        echo ""
        echo "💡 Check Python dependencies: pip install google-cloud-bigquery"
        echo "   Check BigQuery permissions and table schema"
        exit 1
    fi
fi

echo ""
echo "================================================================"
echo "📍 Step 5: View Results in Dashboards"
echo "================================================================"
echo ""
echo "After processing completes, check:"
echo ""
echo "   📊 Exception Dashboard (port 3000):"
echo "      http://localhost:3000"
echo "      - Shows invoices with exceptions"
echo ""
echo "   📋 Invoice Testing App (port 3001):"
echo "      http://localhost:3001"
echo "      - Shows all processed invoices"
echo ""
echo "   🔍 BigQuery Tables:"
if [ "$IS_EXCEPTION" = "true" ]; then
    echo "      Exceptions: SELECT * FROM \`${PROJECT_ID}.invoice_processing.exceptions\` WHERE gcs_uri = '${GCS_URI}'"
else
    echo "      Processed: SELECT * FROM \`${PROJECT_ID}.invoice_processing.invoices_processed\` WHERE gcs_uri = '${GCS_URI}'"
fi

# Calculate total time
TOTAL_END_TIME=$(date +%s)
TOTAL_DURATION=$((TOTAL_END_TIME - TOTAL_START_TIME))
TOTAL_MINUTES=$((TOTAL_DURATION / 60))
TOTAL_SECONDS=$((TOTAL_DURATION % 60))

echo ""
echo "📝 Processing Summary:"
echo "   Message ID: ${MESSAGE_ID}"
echo "   GCS URI: ${GCS_URI}"
echo "   Has Exceptions: ${IS_EXCEPTION}"
echo ""
echo "⏱️  Total Time: ${TOTAL_MINUTES}m ${TOTAL_SECONDS}s"
echo ""
echo "💡 Tip: Refresh the dashboards to see the new invoice"
echo "   (May take a few seconds for BigQuery to be visible)"

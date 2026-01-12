"""
Invoice Exception Management API - With Optional Auth
"""
from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from google.cloud import bigquery
from google.cloud import storage
from fastapi.responses import StreamingResponse
import os
import uuid
import json



app = FastAPI(
    title="Invoice Exception Management API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

project_id = os.getenv("GCP_PROJECT_ID", "consulevent-ap-invoice")
dataset_id = os.getenv("BIGQUERY_DATASET", "invoice_processing")
bq_client = bigquery.Client(project=project_id)

# Disable auth for local development
USE_AUTH = False


async def verify_token(authorization: Optional[str] = Header(None)):
    """Optional auth verification"""
    if not USE_AUTH:
        return {"email": "local-dev@example.com"}
    # Auth code here if needed
    return {}


class ExceptionUpdate(BaseModel):
    status: str
    reviewed_by: str
    review_comments: Optional[str] = None


class ExceptionResponse(BaseModel):
    exception_id: str
    invoice_id: str
    filename: str
    supplier_name: Optional[str]
    total_amount: Optional[float]
    exception_type: str
    exception_severity: str
    status: str
    created_at: datetime
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]


@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Invoice Exception Management API",
        "auth_enabled": USE_AUTH
    }


@app.get("/api/exceptions", response_model=List[ExceptionResponse])
async def list_exceptions(
    authorization: Optional[str] = Header(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, le=1000)
):
    """Get exceptions with latest review status"""
    await verify_token(authorization)
    
    query = f"""
    WITH latest_reviews AS (
      SELECT 
        exception_id,
        status as review_status,
        reviewed_by,
        reviewed_at,
        ROW_NUMBER() OVER (PARTITION BY exception_id ORDER BY reviewed_at DESC) as rn
      FROM `{project_id}.{dataset_id}.exception_reviews`
    )
    SELECT 
        e.exception_id,
        e.invoice_id,
        e.filename,
        e.supplier_name,
        e.total_amount,
        e.exception_type,
        e.exception_severity,
        COALESCE(r.review_status, e.status) as status,
        e.created_at,
        r.reviewed_by,
        r.reviewed_at
    FROM `{project_id}.{dataset_id}.exceptions` e
    LEFT JOIN latest_reviews r ON e.exception_id = r.exception_id AND r.rn = 1
    WHERE 1=1
    """
    
    if status:
        query += f" AND COALESCE(r.review_status, e.status) = '{status}'"
    if severity:
        query += f" AND e.exception_severity = '{severity}'"
    if start_date:
        query += f" AND e.received_date >= '{start_date}'"
    if end_date:
        query += f" AND e.received_date <= '{end_date}'"
    
    query += f" ORDER BY e.created_at DESC LIMIT {limit}"
    
    try:
        query_job = bq_client.query(query)
        results = query_job.result()
        
        exceptions = []
        for row in results:
            exceptions.append({
                "exception_id": row.exception_id,
                "invoice_id": row.invoice_id,
                "filename": row.filename,
                "supplier_name": row.supplier_name,
                "total_amount": row.total_amount,
                "exception_type": row.exception_type,
                "exception_severity": row.exception_severity,
                "status": row.status,
                "created_at": row.created_at,
                "reviewed_by": row.reviewed_by,
                "reviewed_at": row.reviewed_at
            })
        
        return exceptions
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/exceptions/{exception_id}")
async def get_exception(
    exception_id: str,
    authorization: Optional[str] = Header(None)
):
    """Get exception with latest review"""
    await verify_token(authorization)
    
    query = f"""
    WITH latest_review AS (
      SELECT 
        exception_id,
        status as review_status,
        reviewed_by,
        reviewed_at,
        review_comments
      FROM `{project_id}.{dataset_id}.exception_reviews`
      WHERE exception_id = @exception_id
      ORDER BY reviewed_at DESC
      LIMIT 1
    )
    SELECT 
        e.*,
        r.review_status,
        r.reviewed_by as latest_reviewed_by,
        r.reviewed_at as latest_reviewed_at,
        r.review_comments as latest_review_comments
    FROM `{project_id}.{dataset_id}.exceptions` e
    LEFT JOIN latest_review r ON e.exception_id = r.exception_id
    WHERE e.exception_id = @exception_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id)
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if not results:
            raise HTTPException(status_code=404, detail="Exception not found")
        
        row = results[0]
        
        return {
            "exception_id": row.exception_id,
            "invoice_id": row.invoice_id,
            "message_id": row.message_id,
            "filename": row.filename,
            "gcs_uri": row.gcs_uri,
            "received_date": row.received_date.isoformat() if row.received_date else None,
            "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
            "supplier_name": row.supplier_name,
            "total_amount": row.total_amount,
            "exception_type": row.exception_type,
            "exception_severity": row.exception_severity,
            "all_exceptions": row.all_exceptions,
            "status": row.review_status if row.review_status else row.status,
            "reviewed_by": row.latest_reviewed_by,
            "reviewed_at": row.latest_reviewed_at.isoformat() if row.latest_reviewed_at else None,
            "review_comments": row.latest_review_comments,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "raw_extracted_data": row.raw_extracted_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.put("/api/exceptions/{exception_id}")
async def update_exception(
    exception_id: str,
    update: ExceptionUpdate,
    authorization: Optional[str] = Header(None)
):
    """Insert review record"""
    await verify_token(authorization)
    
    valid_statuses = ["PENDING", "APPROVED", "REJECTED"]
    if update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status")
    
    review_id = str(uuid.uuid4())
    query = f"""
    INSERT INTO `{project_id}.{dataset_id}.exception_reviews`
    (review_id, exception_id, status, reviewed_by, reviewed_at, review_comments)
    VALUES (@review_id, @exception_id, @status, @reviewed_by, CURRENT_TIMESTAMP(), @review_comments)
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("review_id", "STRING", review_id),
            bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id),
            bigquery.ScalarQueryParameter("status", "STRING", update.status),
            bigquery.ScalarQueryParameter("reviewed_by", "STRING", update.reviewed_by),
            bigquery.ScalarQueryParameter("review_comments", "STRING", update.review_comments or "")
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()
        
        audit_id = str(uuid.uuid4())
        audit_query = f"""
        INSERT INTO `{project_id}.{dataset_id}.audit_trail`
        (audit_id, exception_id, action, action_by, action_date, action_timestamp, comments)
        VALUES (@audit_id, @exception_id, @action, @action_by, CURRENT_DATE(), CURRENT_TIMESTAMP(), @comments)
        """
        
        audit_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("audit_id", "STRING", audit_id),
                bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id),
                bigquery.ScalarQueryParameter("action", "STRING", update.status),
                bigquery.ScalarQueryParameter("action_by", "STRING", update.reviewed_by),
                bigquery.ScalarQueryParameter("comments", "STRING", update.review_comments or "")
            ]
        )
        
        audit_job = bq_client.query(audit_query, job_config=audit_config)
        audit_job.result()
        
        return {
            "status": "success",
            "message": f"Review submitted for exception {exception_id}",
            "exception_id": exception_id,
            "new_status": update.status,
            "review_id": review_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@app.get("/api/stats")
async def get_statistics(authorization: Optional[str] = Header(None)):
    """Get stats with review statuses"""
    await verify_token(authorization)
    
    query = f"""
    WITH latest_reviews AS (
      SELECT 
        exception_id,
        status,
        ROW_NUMBER() OVER (PARTITION BY exception_id ORDER BY reviewed_at DESC) as rn
      FROM `{project_id}.{dataset_id}.exception_reviews`
    )
    SELECT 
        COALESCE(r.status, e.status) as status,
        e.exception_severity,
        COUNT(*) as count
    FROM `{project_id}.{dataset_id}.exceptions` e
    LEFT JOIN latest_reviews r ON e.exception_id = r.exception_id AND r.rn = 1
    WHERE e.received_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    GROUP BY COALESCE(r.status, e.status), e.exception_severity
    """
    
    try:
        query_job = bq_client.query(query)
        results = query_job.result()
        
        stats = {
            "total_exceptions": 0,
            "by_status": {"PENDING": 0, "APPROVED": 0, "REJECTED": 0},
            "by_severity": {"high": 0, "medium": 0, "low": 0}
        }
        
        for row in results:
            stats["total_exceptions"] += row.count
            stats["by_status"][row.status] = stats["by_status"].get(row.status, 0) + row.count
            stats["by_severity"][row.exception_severity] = stats["by_severity"].get(row.exception_severity, 0) + row.count
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats query failed: {str(e)}")

@app.get("/api/invoices/all")
async def get_all_invoices(
    authorization: Optional[str] = Header(None),
    limit: int = Query(100, le=1000)
):
    """Get all processed invoices for testing"""
    await verify_token(authorization)
    
    query = f"""
    SELECT 
        invoice_id,
        supplier_name,
        invoice_date,
        total_amount,
        gcs_uri,
        line_items,
        raw_extracted_data
    FROM `{project_id}.{dataset_id}.invoices_processed`
    ORDER BY received_date DESC
    LIMIT {limit}
    """
    
    try:
        query_job = bq_client.query(query)
        results = query_job.result()
        
        invoices = []
        for row in results:
            invoices.append({
                "invoice_id": row.invoice_id,
                "supplier_name": row.supplier_name,
                "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
                "total_amount": row.total_amount,
                "gcs_uri": row.gcs_uri,
                "status": "PROCESSED",  # invoices_processed table doesn't have status column
                "line_items": row.line_items if hasattr(row, 'line_items') else None,
                "raw_extracted_data": row.raw_extracted_data if hasattr(row, 'raw_extracted_data') else None
            })
        
        return invoices
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: str,
    authorization: Optional[str] = Header(None)
):
    """Serve PDF file from GCS for an invoice"""
    await verify_token(authorization)
    
    # Get GCS URI from BigQuery
    query = f"""
    SELECT gcs_uri
    FROM `{project_id}.{dataset_id}.invoices_processed`
    WHERE invoice_id = @invoice_id
    LIMIT 1
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id)
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if not results:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        gcs_uri = results[0].gcs_uri
        if not gcs_uri:
            raise HTTPException(status_code=404, detail="PDF not found for this invoice")
        
        # Parse GCS URI: gs://bucket-name/path/to/file.pdf
        if not gcs_uri.startswith('gs://'):
            raise HTTPException(status_code=400, detail="Invalid GCS URI")
        
        gcs_path = gcs_uri[5:]  # Remove 'gs://' prefix
        bucket_name, blob_path = gcs_path.split('/', 1)
        
        # Get file from GCS
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        if not blob.exists():
            raise HTTPException(status_code=404, detail="PDF file not found in GCS")
        
        # Download file from GCS and return it
        file_content = blob.download_as_bytes()
        
        return StreamingResponse(
            iter([file_content]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{blob_path.split("/")[-1]}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve PDF: {str(e)}")


@app.post("/api/test/write-to-bq")
async def write_to_bigquery(
    request: dict,
    authorization: Optional[str] = Header(None)
):
    """
    Test endpoint to write invoice data to BigQuery
    This writes to either invoices_processed or exceptions table based on validation result
    """
    await verify_token(authorization)
    
    try:
        message_id = request.get("message_id")
        filename = request.get("filename")
        gcs_uri = request.get("gcs_uri")
        extracted_data = request.get("extracted_data", {})
        validation_result = request.get("validation_result", {})
        
        if not all([message_id, filename, gcs_uri]):
            raise HTTPException(status_code=400, detail="Missing required fields: message_id, filename, gcs_uri")
        
        is_exception = validation_result.get("is_exception", False)
        exceptions = validation_result.get("exceptions", [])
        
        # Extract invoice data
        invoice_id = extracted_data.get("invoice_id", "UNKNOWN")
        supplier_name = extracted_data.get("supplier_name")
        invoice_date = extracted_data.get("invoice_date")
        total_amount = extracted_data.get("total_amount")
        net_amount = extracted_data.get("net_amount")
        total_tax_amount = extracted_data.get("total_tax_amount")
        currency = extracted_data.get("currency")
        
        if is_exception and len(exceptions) > 0:
            # Write to exceptions table
            exception_id = f"{message_id}-{filename}"
            exception_type = exceptions[0].get("type", "VALIDATION_ERROR")
            exception_severity = exceptions[0].get("severity", "medium")
            
            query = f"""
            INSERT INTO `{project_id}.{dataset_id}.exceptions`
            (exception_id, invoice_id, message_id, filename, gcs_uri, received_date, invoice_date, supplier_name, total_amount, exception_type, exception_severity, all_exceptions, status, raw_extracted_data, created_at)
            VALUES (@exception_id, @invoice_id, @message_id, @filename, @gcs_uri, CURRENT_DATE(), @invoice_date, @supplier_name, @total_amount, @exception_type, @exception_severity, @all_exceptions, 'PENDING', @raw_extracted_data, CURRENT_TIMESTAMP())
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id),
                    bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id),
                    bigquery.ScalarQueryParameter("message_id", "STRING", message_id),
                    bigquery.ScalarQueryParameter("filename", "STRING", filename),
                    bigquery.ScalarQueryParameter("gcs_uri", "STRING", gcs_uri),
                    bigquery.ScalarQueryParameter("invoice_date", "DATE", invoice_date if invoice_date else None),
                    bigquery.ScalarQueryParameter("supplier_name", "STRING", supplier_name),
                    bigquery.ScalarQueryParameter("total_amount", "FLOAT64", float(total_amount) if total_amount else None),
                    bigquery.ScalarQueryParameter("exception_type", "STRING", exception_type),
                    bigquery.ScalarQueryParameter("exception_severity", "STRING", exception_severity),
                    bigquery.ScalarQueryParameter("all_exceptions", "JSON", json.dumps(exceptions)),
                    bigquery.ScalarQueryParameter("raw_extracted_data", "JSON", json.dumps(extracted_data))
                ]
            )
            
            table_name = "exceptions"
        else:
            # Write to invoices_processed table
            query = f"""
            INSERT INTO `{project_id}.{dataset_id}.invoices_processed`
            (invoice_id, message_id, filename, gcs_uri, received_date, invoice_date, supplier_name, total_amount, net_amount, total_tax_amount, currency, raw_extracted_data)
            VALUES (@invoice_id, @message_id, @filename, @gcs_uri, CURRENT_DATE(), @invoice_date, @supplier_name, @total_amount, @net_amount, @total_tax_amount, @currency, @raw_extracted_data)
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id),
                    bigquery.ScalarQueryParameter("message_id", "STRING", message_id),
                    bigquery.ScalarQueryParameter("filename", "STRING", filename),
                    bigquery.ScalarQueryParameter("gcs_uri", "STRING", gcs_uri),
                    bigquery.ScalarQueryParameter("invoice_date", "DATE", invoice_date if invoice_date else None),
                    bigquery.ScalarQueryParameter("supplier_name", "STRING", supplier_name),
                    bigquery.ScalarQueryParameter("total_amount", "FLOAT64", float(total_amount) if total_amount else None),
                    bigquery.ScalarQueryParameter("net_amount", "FLOAT64", float(net_amount) if net_amount else None),
                    bigquery.ScalarQueryParameter("total_tax_amount", "FLOAT64", float(total_tax_amount) if total_tax_amount else None),
                    bigquery.ScalarQueryParameter("currency", "STRING", currency),
                    bigquery.ScalarQueryParameter("raw_extracted_data", "JSON", json.dumps(extracted_data))
                ]
            )
            
            table_name = "invoices_processed"
        
        # Execute the query
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()  # Wait for completion
        
        return {
            "status": "success",
            "message": f"Data written to {table_name} table",
            "table": table_name,
            "invoice_id": invoice_id,
            "is_exception": is_exception
        }
        
    except Exception as e:
        error_message = str(e)
        print(f"Error writing to BigQuery: {error_message}")
        raise HTTPException(status_code=500, detail=f"Failed to write to BigQuery: {error_message}")

@app.get("/api/invoices/{invoice_id}/comments")
async def get_invoice_comments(invoice_id: str):
    """Get comments for an invoice from the comments JSON column"""
    try:
        query = f"""
        SELECT comments
        FROM `{project_id}.{dataset_id}.invoices_processed`
        WHERE invoice_id = @invoice_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id)
            ]
        )
        
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        
        for row in results:
            if row.comments:
                # Parse JSON string to list
                import json
                return json.loads(row.comments) if isinstance(row.comments, str) else row.comments
        
        return []  # No comments found
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/invoices/{invoice_id}/comments")
async def add_invoice_comment(invoice_id: str, comment: dict):
    """Add a comment to the invoice's comments JSON array"""
    try:
        import uuid
        from datetime import datetime, timezone
        import json
        
        comment_id = str(uuid.uuid4())
        created_by = comment.get("created_by", "QA Engineer")
        comment_text = comment.get("comment_text", "")
        
        if not comment_text:
            raise HTTPException(status_code=400, detail="Comment text is required")
        
        new_comment = {
            "comment_id": comment_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
            "comment_text": comment_text,
            "status": "ACTIVE"
        }
        
        # Get existing comments
        query_get = f"""
        SELECT comments
        FROM `{project_id}.{dataset_id}.invoices_processed`
        WHERE invoice_id = @invoice_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id)
            ]
        )
        
        query_job = bq_client.query(query_get, job_config=job_config)
        results = query_job.result()
        
        existing_comments = []
        for row in results:
            if row.comments:
                existing_comments = json.loads(row.comments) if isinstance(row.comments, str) else row.comments
                break
        
        # Add new comment
        existing_comments.append(new_comment)
        comments_json_str = json.dumps(existing_comments)
        
        # Update with new comments array - use PARSE_JSON instead of JSON type
        query_update = f"""
        UPDATE `{project_id}.{dataset_id}.invoices_processed`
        SET comments = PARSE_JSON(@comments)
        WHERE invoice_id = @invoice_id
        """
        
        job_config_update = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id),
                bigquery.ScalarQueryParameter("comments", "STRING", comments_json_str)
            ]
        )
        
        bq_client.query(query_update, job_config=job_config_update).result()
        
        return {
            "success": True,
            "comment_id": comment_id,
            "message": "Comment added successfully"
        }
        
    except Exception as e:
        print(f"Error adding comment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/invoices/{invoice_id}/comments/{comment_id}")
async def delete_comment(invoice_id: str, comment_id: str):
    """Mark a comment as deleted in the comments JSON array"""
    try:
        import json
        
        # Get existing comments
        query_get = f"""
        SELECT comments
        FROM `{project_id}.{dataset_id}.invoices_processed`
        WHERE invoice_id = @invoice_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id)
            ]
        )
        
        query_job = bq_client.query(query_get, job_config=job_config)
        results = query_job.result()
        
        existing_comments = []
        for row in results:
            if row.comments:
                existing_comments = json.loads(row.comments) if isinstance(row.comments, str) else row.comments
                break
        
        # Mark comment as deleted
        for comment in existing_comments:
            if comment.get("comment_id") == comment_id:
                comment["status"] = "DELETED"
        
        comments_json_str = json.dumps(existing_comments)
        
        # Update comments - use PARSE_JSON
        query_update = f"""
        UPDATE `{project_id}.{dataset_id}.invoices_processed`
        SET comments = PARSE_JSON(@comments)
        WHERE invoice_id = @invoice_id
        """
        
        job_config_update = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("invoice_id", "STRING", invoice_id),
                bigquery.ScalarQueryParameter("comments", "STRING", comments_json_str)
            ]
        )
        
        bq_client.query(query_update, job_config=job_config_update).result()
        
        return {"success": True, "message": "Comment deleted"}
        
    except Exception as e:
        print(f"Error deleting comment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/exceptions/{exception_id}/pdf")
async def get_exception_pdf(
    exception_id: str,
    authorization: Optional[str] = Header(None)
):
    """Serve PDF file from GCS for an exception"""
    await verify_token(authorization)
    
    # Get GCS URI from BigQuery exceptions table
    query = f"""
    SELECT gcs_uri
    FROM `{project_id}.{dataset_id}.exceptions`
    WHERE exception_id = @exception_id
    LIMIT 1
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id)
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if not results:
            raise HTTPException(status_code=404, detail="Exception not found")
        
        gcs_uri = results[0].gcs_uri
        if not gcs_uri:
            raise HTTPException(status_code=404, detail="PDF not found for this exception")
        
        # Parse GCS URI: gs://bucket-name/path/to/file.pdf
        if not gcs_uri.startswith('gs://'):
            raise HTTPException(status_code=400, detail="Invalid GCS URI")
        
        gcs_path = gcs_uri[5:]  # Remove 'gs://' prefix
        bucket_name, blob_path = gcs_path.split('/', 1)
        
        # Get file from GCS
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        if not blob.exists():
            raise HTTPException(status_code=404, detail="PDF file not found in GCS")
        
        # Download file from GCS and return it
        file_content = blob.download_as_bytes()
        
        return StreamingResponse(
            iter([file_content]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{blob_path.split("/")[-1]}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve PDF: {str(e)}")

@app.get("/api/exceptions/{exception_id}/comments")
async def get_exception_comments(exception_id: str):
    """Get comments for an exception from the comments JSON column"""
    try:
        query = f"""
        SELECT comments
        FROM `{project_id}.{dataset_id}.exceptions`
        WHERE exception_id = @exception_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id)
            ]
        )
        
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        
        for row in results:
            if row.comments:
                # Parse JSON and filter out deleted comments
                comments = json.loads(row.comments) if isinstance(row.comments, str) else row.comments
                # Only return ACTIVE comments
                return [c for c in comments if c.get("status") == "ACTIVE"]
        
        return []  # No comments found
        
    except Exception as e:
        print(f"Error getting comments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/exceptions/{exception_id}/comments")
async def add_exception_comment(exception_id: str, comment: dict):
    """Add a comment to the exception's comments JSON array"""
    try:
        from datetime import datetime, timezone
        
        comment_id = str(uuid.uuid4())
        created_by = comment.get("created_by", "QA Engineer")
        comment_text = comment.get("comment_text", "")
        
        if not comment_text:
            raise HTTPException(status_code=400, detail="Comment text is required")
        
        new_comment = {
            "comment_id": comment_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
            "comment_text": comment_text,
            "status": "ACTIVE"
        }
        
        # Get existing comments
        query_get = f"""
        SELECT comments
        FROM `{project_id}.{dataset_id}.exceptions`
        WHERE exception_id = @exception_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id)
            ]
        )
        
        query_job = bq_client.query(query_get, job_config=job_config)
        results = query_job.result()
        
        existing_comments = []
        for row in results:
            if row.comments:
                existing_comments = json.loads(row.comments) if isinstance(row.comments, str) else row.comments
                break
        
        # Add new comment
        existing_comments.append(new_comment)
        comments_json_str = json.dumps(existing_comments)
        
        # Update with new comments array
        query_update = f"""
        UPDATE `{project_id}.{dataset_id}.exceptions`
        SET comments = PARSE_JSON(@comments)
        WHERE exception_id = @exception_id
        """
        
        job_config_update = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id),
                bigquery.ScalarQueryParameter("comments", "STRING", comments_json_str)
            ]
        )
        
        bq_client.query(query_update, job_config=job_config_update).result()
        
        return {
            "success": True,
            "comment_id": comment_id,
            "message": "Comment added successfully"
        }
        
    except Exception as e:
        print(f"Error adding comment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/exceptions/{exception_id}/comments/{comment_id}")
async def delete_exception_comment(exception_id: str, comment_id: str):
    """Mark a comment as deleted in the comments JSON array"""
    try:
        # Get existing comments
        query_get = f"""
        SELECT comments
        FROM `{project_id}.{dataset_id}.exceptions`
        WHERE exception_id = @exception_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id)
            ]
        )
        
        query_job = bq_client.query(query_get, job_config=job_config)
        results = query_job.result()
        
        existing_comments = []
        for row in results:
            if row.comments:
                existing_comments = json.loads(row.comments) if isinstance(row.comments, str) else row.comments
                break
        
        # Mark comment as deleted
        for comment in existing_comments:
            if comment.get("comment_id") == comment_id:
                comment["status"] = "DELETED"
        
        comments_json_str = json.dumps(existing_comments)
        
        # Update comments
        query_update = f"""
        UPDATE `{project_id}.{dataset_id}.exceptions`
        SET comments = PARSE_JSON(@comments)
        WHERE exception_id = @exception_id
        """
        
        job_config_update = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id),
                bigquery.ScalarQueryParameter("comments", "STRING", comments_json_str)
            ]
        )
        
        bq_client.query(query_update, job_config=job_config_update).result()
        
        return {"success": True, "message": "Comment deleted"}
        
    except Exception as e:
        print(f"Error deleting comment: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port {port}")
    print(f"Auth enabled: {USE_AUTH}")
    uvicorn.run(app, host="0.0.0.0", port=port)
"""
Invoice Exception Management API - With Optional Auth
"""
from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from typing import List, Optional
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from google.cloud import bigquery
from google.cloud import storage
import os
import uuid
import io

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
    
    # Query without status column (it might not exist in the table schema)
    # We'll default to 'PROCESSED' in the response
    query = f"""
    SELECT 
        invoice_id,
        supplier_name,
        invoice_date,
        total_amount,
        gcs_uri,
        line_items,
        raw_extracted_data,
        received_date
    FROM `{project_id}.{dataset_id}.invoices_processed`
    ORDER BY received_date DESC
    LIMIT {limit}
    """
    
    try:
        query_job = bq_client.query(query)
        results = query_job.result()
        
        invoices = []
        for row in results:
            # Handle None values safely
            invoice_id = row.invoice_id if hasattr(row, 'invoice_id') and row.invoice_id else "UNKNOWN"
            supplier_name = row.supplier_name if hasattr(row, 'supplier_name') else None
            invoice_date = row.invoice_date.isoformat() if hasattr(row, 'invoice_date') and row.invoice_date else None
            total_amount = float(row.total_amount) if hasattr(row, 'total_amount') and row.total_amount is not None else 0.0
            gcs_uri = row.gcs_uri if hasattr(row, 'gcs_uri') else None
            
            invoices.append({
                "invoice_id": invoice_id,
                "supplier_name": supplier_name,
                "invoice_date": invoice_date,
                "total_amount": total_amount,
                "gcs_uri": gcs_uri,
                "status": "PROCESSED",  # Default status since column might not exist
                "line_items": row.line_items if hasattr(row, 'line_items') else None,
                "raw_extracted_data": row.raw_extracted_data if hasattr(row, 'raw_extracted_data') else None
            })
        
        return invoices
    except Exception as e:
        error_message = str(e)
        # Check if table doesn't exist
        if "Not found" in error_message or "does not exist" in error_message or "not found" in error_message.lower():
            raise HTTPException(
                status_code=404, 
                detail=f"Table {project_id}.{dataset_id}.invoices_processed not found. Make sure invoices have been processed and the table exists."
            )
        # Log the full error for debugging
        print(f"Error querying invoices: {error_message}")
        raise HTTPException(status_code=500, detail=f"Query failed: {error_message}")

@app.get("/api/exceptions/{exception_id}/pdf")
async def get_exception_pdf(
    exception_id: str,
    authorization: Optional[str] = Header(None)
):
    """Get PDF file for an exception"""
    await verify_token(authorization)
    
    # First get the exception to retrieve gcs_uri
    query = f"""
    SELECT gcs_uri, filename
    FROM `{project_id}.{dataset_id}.exceptions`
    WHERE exception_id = @exception_id
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
        gcs_uri = row.gcs_uri
        
        if not gcs_uri:
            raise HTTPException(status_code=404, detail="PDF not found for this exception")
        
        # Parse GCS URI (format: gs://bucket-name/path/to/file.pdf)
        gcs_uri = gcs_uri.replace('gs://', '')
        parts = gcs_uri.split('/', 1)
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid GCS URI format")
        
        bucket_name = parts[0]
        blob_path = parts[1]
        
        # Download PDF from GCS
        try:
            storage_client = storage.Client(project=project_id)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                raise HTTPException(status_code=404, detail="PDF file not found in storage")
            
            pdf_content = blob.download_as_bytes()
            filename = row.filename or "invoice.pdf"
            
            # Return PDF as response with proper headers for inline viewing
            return Response(
                content=pdf_content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{filename}"',
                    "Cache-Control": "public, max-age=3600"
                }
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve PDF: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/exceptions/{exception_id}/pdf-url")
async def get_exception_pdf_url(
    exception_id: str,
    authorization: Optional[str] = Header(None)
):
    """Get signed URL for PDF file (alternative to direct download)"""
    await verify_token(authorization)
    
    # First get the exception to retrieve gcs_uri
    query = f"""
    SELECT gcs_uri, filename
    FROM `{project_id}.{dataset_id}.exceptions`
    WHERE exception_id = @exception_id
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
        gcs_uri = row.gcs_uri
        
        if not gcs_uri:
            raise HTTPException(status_code=404, detail="PDF not found for this exception")
        
        # Parse GCS URI
        gcs_uri = gcs_uri.replace('gs://', '')
        parts = gcs_uri.split('/', 1)
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid GCS URI format")
        
        bucket_name = parts[0]
        blob_path = parts[1]
        
        # Generate signed URL
        try:
            storage_client = storage.Client(project=project_id)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                raise HTTPException(status_code=404, detail="PDF file not found in storage")
            
            # Generate signed URL valid for 1 hour
            signed_url = blob.generate_signed_url(
                expiration=timedelta(hours=1),
                method="GET"
            )
            
            return {
                "url": signed_url,
                "filename": row.filename or "invoice.pdf",
                "expires_in": 3600
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate signed URL: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port {port}")
    print(f"Auth enabled: {USE_AUTH}")
    uvicorn.run(app, host="0.0.0.0", port=port)
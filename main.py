"""
Invoice Exception Management API
FastAPI backend for managing invoice processing exceptions
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from google.cloud import bigquery
import os
import uuid

# Initialize FastAPI
app = FastAPI(
    title="Invoice Exception Management API",
    description="Backend API for managing invoice processing exceptions",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# BigQuery client
project_id = os.getenv("GCP_PROJECT_ID", "consulevent-ap-invoice")
dataset_id = os.getenv("BIGQUERY_DATASET", "invoice_processing")
bq_client = bigquery.Client(project=project_id)


# Pydantic Models
class ExceptionFilter(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    supplier_name: Optional[str] = None


class ExceptionUpdate(BaseModel):
    status: str  # APPROVED, REJECTED, PENDING
    reviewed_by: str
    review_comments: Optional[str] = None


class ExceptionComment(BaseModel):
    comment: str
    commented_by: str


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


# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Invoice Exception Management API",
        "version": "1.0.0"
    }


@app.get("/api/exceptions", response_model=List[ExceptionResponse])
async def list_exceptions(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, APPROVED, REJECTED"),
    severity: Optional[str] = Query(None, description="Filter by severity: high, medium, low"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, le=1000, description="Maximum results to return")
):
    """
    Get list of exceptions with optional filtering
    """
    
    # Build query
    query = f"""
    SELECT 
        exception_id,
        invoice_id,
        filename,
        supplier_name,
        total_amount,
        exception_type,
        exception_severity,
        status,
        created_at,
        reviewed_by,
        reviewed_at,
        review_comments,
        all_exceptions,
        raw_extracted_data
    FROM `{project_id}.{dataset_id}.exceptions`
    WHERE 1=1
    """
    
    # Add filters
    if status:
        query += f" AND status = '{status}'"
    
    if severity:
        query += f" AND exception_severity = '{severity}'"
    
    if start_date:
        query += f" AND received_date >= '{start_date}'"
    
    if end_date:
        query += f" AND received_date <= '{end_date}'"
    
    query += f" ORDER BY created_at DESC LIMIT {limit}"
    
    # Execute query
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
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@app.get("/api/exceptions/{exception_id}")
async def get_exception(exception_id: str):
    """
    Get detailed information about a specific exception
    """
    
    query = f"""
    SELECT *
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
            "status": row.status,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "review_comments": row.review_comments,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "raw_extracted_data": row.raw_extracted_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@app.put("/api/exceptions/{exception_id}")
async def update_exception(exception_id: str, update: ExceptionUpdate):
    """
    Update exception status (approve, reject, reassign)
    """
    
    # Validate status
    valid_statuses = ["PENDING", "APPROVED", "REJECTED"]
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    # Update exception in BigQuery (removed updated_at field)
    query = f"""
    UPDATE `{project_id}.{dataset_id}.exceptions`
    SET 
        status = @status,
        reviewed_by = @reviewed_by,
        reviewed_at = CURRENT_TIMESTAMP(),
        review_comments = @review_comments
    WHERE exception_id = @exception_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id),
            bigquery.ScalarQueryParameter("status", "STRING", update.status),
            bigquery.ScalarQueryParameter("reviewed_by", "STRING", update.reviewed_by),
            bigquery.ScalarQueryParameter("review_comments", "STRING", update.review_comments or "")
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()
        
        # Log to audit trail
        audit_id = str(uuid.uuid4())
        audit_query = f"""
        INSERT INTO `{project_id}.{dataset_id}.audit_trail`
        (audit_id, exception_id, action, action_by, action_date, action_timestamp, comments, new_status)
        VALUES (@audit_id, @exception_id, @action, @action_by, CURRENT_DATE(), CURRENT_TIMESTAMP(), @comments, @new_status)
        """
        
        audit_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("audit_id", "STRING", audit_id),
                bigquery.ScalarQueryParameter("exception_id", "STRING", exception_id),
                bigquery.ScalarQueryParameter("action", "STRING", update.status),
                bigquery.ScalarQueryParameter("action_by", "STRING", update.reviewed_by),
                bigquery.ScalarQueryParameter("comments", "STRING", update.review_comments or ""),
                bigquery.ScalarQueryParameter("new_status", "STRING", update.status)
            ]
        )
        
        audit_job = bq_client.query(audit_query, job_config=audit_config)
        audit_job.result()
        
        return {
            "status": "success",
            "message": f"Exception {exception_id} updated to {update.status}",
            "exception_id": exception_id,
            "new_status": update.status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@app.get("/api/stats")
async def get_statistics():
    """
    Get dashboard statistics
    """
    
    query = f"""
    SELECT 
        status,
        exception_severity,
        COUNT(*) as count
    FROM `{project_id}.{dataset_id}.exceptions`
    WHERE received_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    GROUP BY status, exception_severity
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

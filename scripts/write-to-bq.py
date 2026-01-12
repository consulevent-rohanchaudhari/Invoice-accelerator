#!/usr/bin/env python3
"""
Helper script to write invoice data to BigQuery
Uses parameterized queries like the backend to properly handle JSON
"""
import sys
import json
from datetime import datetime
from google.cloud import bigquery

def parse_date(date_str):
    """Parse date string to date object, return None if invalid format"""
    if not date_str or date_str == "null":
        return None
    try:
        # Try YYYY-MM-DD format first
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        # Try M/D/YYYY format (e.g., "6/4/2025")
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                month, day, year = parts
                return datetime.strptime(f"{year}-{month.zfill(2)}-{day.zfill(2)}", "%Y-%m-%d").date()
        return None
    except (ValueError, IndexError):
        return None

def write_to_bigquery(table_name, data):
    project_id = "consulevent-ap-invoice"
    dataset_id = "invoice_processing"
    
    client = bigquery.Client(project=project_id)
    
    if table_name == "invoices_processed":
        query = f"""
        INSERT INTO `{project_id}.{dataset_id}.invoices_processed`
        (invoice_id, message_id, filename, gcs_uri, received_date, invoice_date, supplier_name, total_amount, net_amount, total_tax_amount, currency, raw_extracted_data)
        VALUES (@invoice_id, @message_id, @filename, @gcs_uri, CURRENT_DATE(), @invoice_date, @supplier_name, @total_amount, @net_amount, @total_tax_amount, @currency, PARSE_JSON(@raw_extracted_data))
        """
        
        raw_data_json = json.dumps(data["raw_extracted_data"]) if data.get("raw_extracted_data") else "{}"
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("invoice_id", "STRING", data["invoice_id"]),
                bigquery.ScalarQueryParameter("message_id", "STRING", data["message_id"]),
                bigquery.ScalarQueryParameter("filename", "STRING", data["filename"]),
                bigquery.ScalarQueryParameter("gcs_uri", "STRING", data["gcs_uri"]),
                bigquery.ScalarQueryParameter("invoice_date", "DATE", parse_date(data.get("invoice_date"))),
                bigquery.ScalarQueryParameter("supplier_name", "STRING", data.get("supplier_name")),
                bigquery.ScalarQueryParameter("total_amount", "FLOAT64", float(data["total_amount"]) if data.get("total_amount") else None),
                bigquery.ScalarQueryParameter("net_amount", "FLOAT64", float(data["net_amount"]) if data.get("net_amount") else None),
                bigquery.ScalarQueryParameter("total_tax_amount", "FLOAT64", float(data["total_tax_amount"]) if data.get("total_tax_amount") else None),
                bigquery.ScalarQueryParameter("currency", "STRING", data.get("currency")),
                bigquery.ScalarQueryParameter("raw_extracted_data", "STRING", raw_data_json)
            ]
        )
    else:  # exceptions
        query = f"""
        INSERT INTO `{project_id}.{dataset_id}.exceptions`
        (exception_id, invoice_id, message_id, filename, gcs_uri, received_date, invoice_date, supplier_name, total_amount, exception_type, exception_severity, all_exceptions, status, raw_extracted_data)
        VALUES (@exception_id, @invoice_id, @message_id, @filename, @gcs_uri, CURRENT_DATE(), @invoice_date, @supplier_name, @total_amount, @exception_type, @exception_severity, PARSE_JSON(@all_exceptions), 'PENDING', PARSE_JSON(@raw_extracted_data))
        """
        
        all_exceptions_json = json.dumps(data["all_exceptions"]) if data.get("all_exceptions") else "[]"
        raw_data_json = json.dumps(data["raw_extracted_data"]) if data.get("raw_extracted_data") else "{}"
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("exception_id", "STRING", data["exception_id"]),
                bigquery.ScalarQueryParameter("invoice_id", "STRING", data["invoice_id"]),
                bigquery.ScalarQueryParameter("message_id", "STRING", data["message_id"]),
                bigquery.ScalarQueryParameter("filename", "STRING", data["filename"]),
                bigquery.ScalarQueryParameter("gcs_uri", "STRING", data["gcs_uri"]),
                bigquery.ScalarQueryParameter("invoice_date", "DATE", parse_date(data.get("invoice_date"))),
                bigquery.ScalarQueryParameter("supplier_name", "STRING", data.get("supplier_name")),
                bigquery.ScalarQueryParameter("total_amount", "FLOAT64", float(data["total_amount"]) if data.get("total_amount") else None),
                bigquery.ScalarQueryParameter("exception_type", "STRING", data["exception_type"]),
                bigquery.ScalarQueryParameter("exception_severity", "STRING", data["exception_severity"]),
                bigquery.ScalarQueryParameter("all_exceptions", "STRING", all_exceptions_json),
                bigquery.ScalarQueryParameter("raw_extracted_data", "STRING", raw_data_json)
            ]
        )
    
    try:
        query_job = client.query(query, job_config=job_config)
        query_job.result()  # Wait for completion
        print("SUCCESS")
        return 0
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: write-to-bq.py <table_name> <json_data>", file=sys.stderr)
        sys.exit(1)
    
    table_name = sys.argv[1]
    json_data = json.loads(sys.argv[2])
    
    sys.exit(write_to_bigquery(table_name, json_data))

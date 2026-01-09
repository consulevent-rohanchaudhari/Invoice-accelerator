# Invoice-accelerator

Enterprise invoice and purchase order processing system using GCP Document AI and Gemini.

## Overview

This system automates the processing of invoices and POs received via email:
- Email integration with Outlook
- Document AI for data extraction
- Gemini for low-confidence field synthesis
- Automated validation with exception handling
- Analyst dashboard for exception review

## Tech Stack

- **GCP**: Cloud Workflows, Cloud Functions, Document AI, Vertex AI, BigQuery, Cloud Storage, Pub/Sub, Cloud Run
- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: React + Vite + Tailwind CSS

## Project Structure
```
invoice-po-accelerator/
├── backend/              # FastAPI application
├── cloud-functions/      # Processing pipeline functions
├── workflows/            # Cloud Workflows orchestration
├── frontend/             # React dashboard
├── config/               # Configuration files
└── docs/                 # Documentation
```

## Setup

Detailed setup instructions will be added as we build out each component.

## License

Proprietary - Consulevent Inc.
```
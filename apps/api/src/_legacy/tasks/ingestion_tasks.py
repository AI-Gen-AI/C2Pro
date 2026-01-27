"""
C2Pro - Asynchronous Ingestion Tasks

This module defines Celery tasks related to document ingestion and processing.
These tasks are designed to run in the background, decoupled from the main
API request/response cycle.
"""
import time
import random
import logging

from src.core.celery_app import celery_app
from src.services.ingestion.pdf_parser import PdfParserService

logger = logging.getLogger(__name__)

# --- Mock Database and Storage ---
# In a real application, these would be proper database models and storage clients.
MOCK_DB = {}
MOCK_STORAGE = {}

def _get_document_from_db(doc_id: str) -> dict:
    """Simulates fetching a document record from the database."""
    logger.info(f"TASK: Fetching document '{doc_id}' from DB.")
    return MOCK_DB.get(doc_id)

def _get_file_from_storage(file_path: str) -> bytes:
    """Simulates fetching a file from a storage service like S3 or a local disk."""
    logger.info(f"TASK: Fetching file content from storage path '{file_path}'.")
    return MOCK_STORAGE.get(file_path)

def _update_document_status_in_db(doc_id: str, status: str, details: dict = None):
    """Simulates updating a document's status in the database."""
    logger.info(f"TASK: Updating document '{doc_id}' status to '{status}'.")
    if doc_id in MOCK_DB:
        MOCK_DB[doc_id]['status'] = status
        MOCK_DB[doc_id]['processing_details'] = details
        MOCK_DB[doc_id]['processed_at'] = time.time()
        logger.info(f"TASK: Document '{doc_id}' state: {MOCK_DB[doc_id]}")
    else:
        logger.error(f"TASK: Document '{doc_id}' not found in DB for status update.")

# --- Task Definition ---

@celery_app.task(
    bind=True,               # Makes 'self' available in the task context
    autoretry_for=(Exception,), # Automatically retry on any exception
    retry_kwargs={'max_retries': 3}, # Max 3 retries
    retry_backoff=True,      # Exponential backoff (e.g., 2s, 4s, 8s)
    retry_backoff_max=60,    # Max delay between retries is 60 seconds
    task_track_started=True
)
def process_document_async(self, document_id: str):
    """
    Asynchronously processes a document using the appropriate parser.

    Args:
        document_id: The unique ID of the document to process. The task
                     retrieves the file path and other info from the database.
    """
    logger.info(f"Starting document processing for task_id: {self.request.id}, document_id: {document_id}")

    # 1. Retrieve document metadata from the database
    document_record = _get_document_from_db(document_id)
    if not document_record:
        logger.error(f"Document with ID '{document_id}' not found. Cannot process.")
        # Do not retry if the document doesn't exist.
        return {"status": "error", "message": "Document not found"}

    _update_document_status_in_db(document_id, "PROCESSING")

    try:
        # 2. Retrieve the file content from storage
        file_content = _get_file_from_storage(document_record["storage_path"])
        if not file_content:
            raise FileNotFoundError(f"File content for document '{document_id}' not found in storage.")

        # 3. Select and run the appropriate parser (example for PDF)
        # In a real scenario, you would have a factory or switch-case here based on file type.
        if document_record["file_type"] == "pdf":
            parser = PdfParserService()
            parsed_data = parser.extract_text(file_content, filename=document_record["filename"])
            
            # For demonstration, we'll just log some stats.
            # In a real app, you would save `parsed_data` to the DB or another service.
            processing_details = {
                "pages_processed": parsed_data["page_count"],
                "tables_found": len(parsed_data.get("tables_data", [])),
                "chars_extracted": len(parsed_data["full_text"])
            }
            logger.info("PDF parsing successful.")
            
        else:
            # Placeholder for other parsers (Excel, BC3, etc.)
            logger.warning(f"No parser available for file type '{document_record['file_type']}'.")
            processing_details = {"error": "Unsupported file type"}

        # 4. Update the document status to PARSED
        _update_document_status_in_db(document_id, "PARSED", details=processing_details)
        
        return {"status": "success", "document_id": document_id, "details": processing_details}

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
        # Update status to ERROR
        _update_document_status_in_db(document_id, "ERROR", details={"error_message": str(e)})
        # The 'autoretry_for' decorator will handle re-raising and retrying the task.
        raise


def trigger_test_task():
    """
    A helper function to simulate an API endpoint triggering the task.
    This would typically be called from a FastAPI router.
    """
    logger.info("API: Received request to upload and process a document.")
    
    # 1. API receives file, saves it to storage, creates DB record
    doc_id = f"doc_{random.randint(1000, 9999)}"
    filename = f"{doc_id}_contract.pdf"
    storage_path = f"uploads/{filename}"
    
    # Create some dummy PDF content for the mock storage
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="This is a test PDF for C2Pro.", ln=1, align="C")
    dummy_pdf_content = pdf.output(dest='S').encode('latin-1')

    MOCK_STORAGE[storage_path] = dummy_pdf_content
    MOCK_DB[doc_id] = {
        "id": doc_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_type": "pdf",
        "status": "UPLOADED",
        "created_at": time.time(),
    }
    logger.info(f"API: Document '{doc_id}' saved. Record created in DB.")

    # 2. Enqueue the processing task
    logger.info(f"API: Enqueuing 'process_document_async' task for document_id: {doc_id}")
    task = process_document_async.delay(document_id=doc_id)
    
    # 3. API responds immediately with the task ID
    response = {"message": "Document accepted for processing.", "task_id": task.id, "document_id": doc_id}
    logger.info(f"API: Responding 202 Accepted. Response: {response}")
    return response

if __name__ == '__main__':
    # This block allows for simple, direct testing of the task flow.
    # To run this, you need a Redis server running and a Celery worker started.
    # Worker command: celery -A apps.api.src.core.celery_app.celery_app worker -l info -P gevent
    logging.basicConfig(level=logging.INFO)
    print("--- Triggering a test document processing task ---")
    trigger_test_task()
    print("--- Task enqueued. Check the Celery worker logs for processing details. ---")

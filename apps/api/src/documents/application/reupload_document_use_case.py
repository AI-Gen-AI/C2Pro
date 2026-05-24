"""
Use Case for re-uploading a document (document update with version increment).
Part of TASK-BCK-023
"""
import hashlib
from uuid import UUID

from src.documents.application.dtos import DocumentDTO
from src.documents.domain.models import DocumentStatus
from src.documents.ports.document_repository import IDocumentRepository


class ReuploadDocumentUseCase:
    """
    Handles document re-upload with version tracking and analysis cancellation.

    Flow:
    1. Calculate file hash of new content
    2. Compare with existing file hash
    3. If different:
       - Increment version
       - Update file_hash
       - Cancel in-progress analysis (reset status to UPLOADED)
       - Trigger re-ingestion
    4. If same:
       - Return existing document (no changes)
    """

    def __init__(self, document_repository: IDocumentRepository):
        self.document_repository = document_repository

    async def execute(
        self,
        tenant_id: UUID,
        document_id: UUID,
        file_content: bytes,
        filename: str | None = None,
    ) -> DocumentDTO:
        """
        Re-upload a document with version tracking.

        Args:
            tenant_id: Current tenant ID
            document_id: ID of document to re-upload
            file_content: New file content
            filename: Optional new filename

        Returns:
            DocumentDTO with updated version and status

        Raises:
            ValueError: If document not found
        """
        # Get existing document
        document = await self.document_repository.get_by_id(tenant_id, document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        # Calculate file hash of new content
        new_file_hash = hashlib.sha256(file_content).hexdigest()

        # Check if content has changed
        if document.file_hash == new_file_hash:
            # Same content, no version increment
            return DocumentDTO.from_domain(document)

        # Different content - increment version and reset for re-processing
        new_version = document.version + 1

        # Update document
        updated_document = await self.document_repository.update_version(
            tenant_id=tenant_id,
            document_id=document_id,
            version=new_version,
            file_hash=new_file_hash,
            filename=filename or document.filename,
            status=DocumentStatus.UPLOADED,  # Reset for re-processing
        )

        await self.document_repository.commit()

        return DocumentDTO.from_domain(updated_document)

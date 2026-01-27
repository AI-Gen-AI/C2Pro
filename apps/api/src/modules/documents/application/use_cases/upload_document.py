from uuid import UUID
from fastapi import UploadFile

from apps.api.src.modules.documents.domain.models import Document, DocumentType

class UploadDocumentUseCase:
    def __init__(self):
        # Dependencies will be injected here
        pass

    async def execute(
        self,
        project_id: UUID,
        file: UploadFile,
        document_type: DocumentType,
        user_id: UUID,
        metadata: dict = None,
    ) -> Document:
        # TODO: Implement the logic from DocumentService.upload_document
        raise NotImplementedError

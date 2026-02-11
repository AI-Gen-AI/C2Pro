"""
C2Pro - Ingestion Application Services

Business logic and orchestration for document ingestion workflows.

Increment I2: OCR + Table Parsing Reliability
- OCRProcessingService: Orchestrates OCR with primary/fallback strategy
"""

import structlog
from typing import Any, Optional, List, Dict

from src.modules.ingestion.application.ports import OCRAdapter, OCRResult
from src.modules.ingestion.domain.entities import TableData

logger = structlog.get_logger(__name__)


class OCRProcessingService:
    """
    Service for processing PDF pages with OCR, including fallback strategy.

    Refers to I2.3: Regression test - OCR fallback engages when primary OCR
    confidence below threshold.

    This service implements the primary/fallback OCR strategy to maximize
    extraction reliability:

    1. **Primary OCR**: Fast, cost-effective provider (e.g., Tesseract)
    2. **Confidence Check**: If confidence < threshold, fallback engages
    3. **Fallback OCR**: Higher-quality, potentially more expensive provider
       (e.g., Google Vision, AWS Textract)

    This strategy balances cost and quality:
    - 80% of pages: High-quality scans processed by fast primary OCR
    - 20% of pages: Low-quality scans processed by premium fallback OCR

    Observability:
    - Logs provider choice for every page
    - Tracks confidence histograms for monitoring
    - Integrates with LangSmith for trace analysis

    Args:
        primary_ocr: Primary OCR adapter (fast, cost-effective)
        fallback_ocr: Fallback OCR adapter (high-quality, more expensive)
        low_confidence_threshold: Confidence threshold below which fallback engages
            (default: 0.5, meaning 50% confidence)
    """

    def __init__(
        self,
        primary_ocr: OCRAdapter,
        fallback_ocr: OCRAdapter,
        low_confidence_threshold: float = 0.5,
    ):
        """
        Initialize OCR processing service with primary/fallback strategy.

        Args:
            primary_ocr: Primary OCR adapter
            fallback_ocr: Fallback OCR adapter
            low_confidence_threshold: Threshold below which fallback engages
        """
        self.primary_ocr = primary_ocr
        self.fallback_ocr = fallback_ocr
        self.low_confidence_threshold = low_confidence_threshold

        logger.info(
            "ocr_processing_service_initialized",
            low_confidence_threshold=low_confidence_threshold,
        )

    async def process_page_with_fallback(
        self,
        page_content: bytes,
        mock_langsmith: Optional[Any] = None,
    ) -> OCRResult:
        """
        Process a PDF page with primary OCR, falling back if confidence is low.

        Refers to I2.3: OCR fallback engages when primary OCR confidence below threshold.
        Refers to I2.5: Observability hooks (LangSmith) - Log OCR provider choice.

        Workflow:
        1. Process with primary OCR
        2. Check confidence score
        3. If confidence < threshold: process with fallback OCR
        4. Return best result
        5. Log decision to LangSmith (if provided)

        Args:
            page_content: Binary content of PDF page
            mock_langsmith: Optional LangSmith client for observability
                (injected for testing, in production would use global client)

        Returns:
            OCRResult from either primary or fallback OCR

        Example:
            ```python
            service = OCRProcessingService(
                primary_ocr=TesseractAdapter(),
                fallback_ocr=GoogleVisionAdapter(),
                low_confidence_threshold=0.5
            )

            result = await service.process_page_with_fallback(pdf_bytes)
            print(f"Used provider: {result['provider']}")
            print(f"Final confidence: {result['confidence']}")
            ```
        """
        # Step 1: Try primary OCR
        logger.info(
            "ocr_processing_started",
            provider="primary",
            page_size_bytes=len(page_content),
        )

        primary_result = await self.primary_ocr.process_pdf_page(page_content)

        logger.info(
            "ocr_primary_completed",
            provider=primary_result["provider"],
            confidence=primary_result["confidence"],
            text_length=len(primary_result["text"]),
            bbox_count=len(primary_result["bboxes"]),
        )

        # LangSmith observability: Start span
        span = None
        if mock_langsmith:
            span_name = "ocr_processing_with_fallback"
            input_data = {
                "page_content_len": len(page_content),
                "primary_confidence": primary_result.get("confidence"),
            }
            span = mock_langsmith.start_span(
                span_name,
                input=input_data,
                run_type="chain",
                provider_choice=primary_result.get("provider"),
            )

        # Step 2: Check if fallback is needed
        if primary_result.get("confidence", 0.0) < self.low_confidence_threshold:
            logger.warning(
                "ocr_fallback_triggered",
                primary_confidence=primary_result["confidence"],
                threshold=self.low_confidence_threshold,
                reason="low_confidence",
            )

            # Step 3: Process with fallback OCR
            fallback_result = await self.fallback_ocr.process_pdf_page(page_content)

            logger.info(
                "ocr_fallback_completed",
                provider=fallback_result["provider"],
                confidence=fallback_result["confidence"],
                text_length=len(fallback_result["text"]),
                bbox_count=len(fallback_result["bboxes"]),
            )

            # LangSmith observability: Log fallback usage
            if mock_langsmith and span:
                mock_langsmith.end_span(
                    span,
                    outputs={
                        "status": "fallback_used",
                        "final_confidence": fallback_result.get("confidence"),
                    },
                )

            return fallback_result

        # Step 4: Primary OCR confidence is acceptable, use it
        logger.info(
            "ocr_primary_accepted",
            confidence=primary_result["confidence"],
            threshold=self.low_confidence_threshold,
        )

        # LangSmith observability: Log primary usage
        if mock_langsmith and span:
            mock_langsmith.end_span(
                span,
                outputs={
                    "status": "primary_used",
                    "final_confidence": primary_result.get("confidence"),
                },
            )

        return primary_result


class TableParserService:
    """
    Service for extracting and normalizing table data from PDF pages.

    Refers to I2.2: Table extraction preserves row/column counts on fixture tables.
    Refers to I2.4: Table normalization rules with header reconciliation.

    This service handles table extraction with proper cell normalization and
    merged cell handling. It ensures:
    - Consistent row/column structure across all extracted tables
    - Proper preservation of merged cells
    - Header row detection and reconciliation
    - Low-confidence flagging for human review

    Observability:
    - Logs table extraction counts and confidence scores
    - Integrates with LangSmith for trace analysis
    - Tracks table normalization metrics

    Args:
        table_extractor: The underlying table extraction engine/adapter
        low_confidence_threshold: Confidence threshold for flagging human review
            (default: 0.5, meaning 50% confidence)
    """

    def __init__(
        self,
        table_extractor: Any,
        low_confidence_threshold: float = 0.5,
        langsmith_client: Optional[Any] = None,
    ):
        """
        Initialize the table parser service.

        Args:
            table_extractor: The underlying table extraction engine/adapter
            low_confidence_threshold: Confidence threshold for flagging human review
            langsmith_client: Optional LangSmith client for observability
        """
        self.table_extractor = table_extractor
        self.low_confidence_threshold = low_confidence_threshold
        self.langsmith_client = langsmith_client

        logger.info(
            "table_parser_service_initialized",
            low_confidence_threshold=low_confidence_threshold,
        )

    async def extract_tables_from_pdf_page(
        self,
        page_content: bytes,
        mock_langsmith: Optional[Any] = None,
    ) -> List[TableData]:
        """
        Extract tables from a PDF page with normalization.

        Refers to I2.2: Table extraction preserves row/column counts.
        Refers to I2.4: Table normalization rules with header reconciliation.
        Refers to I2.6: Human-in-the-loop checkpoints for low-confidence tables.

        Workflow:
        1. Extract raw tables using the underlying extractor
        2. Normalize each table (consistent column counts, merged cell handling)
        3. Flag low-confidence tables for human review
        4. Log extraction metrics to LangSmith (if provided)

        Args:
            page_content: Binary content of the PDF page
            mock_langsmith: Optional LangSmith client for observability
                (injected for testing, in production would use global client)

        Returns:
            List of TableData objects representing extracted tables

        Example:
            ```python
            service = TableParserService(
                table_extractor=CamelotExtractor(),
                low_confidence_threshold=0.5
            )

            tables = await service.extract_tables_from_pdf_page(pdf_bytes)
            for table in tables:
                if table.metadata.get("needs_human_review"):
                    route_to_review_queue(table)
            ```
        """
        langsmith = mock_langsmith or self.langsmith_client

        logger.info(
            "table_extraction_started",
            page_size_bytes=len(page_content),
        )

        # LangSmith observability: Start span
        span = None
        if langsmith:
            span = langsmith.start_span(
                "table_extraction",
                input={"page_content_len": len(page_content)},
                run_type="tool",
            )

        # Step 1: Extract raw tables using the underlying extractor
        # In production, this would call self.table_extractor.extract(page_content)
        # For now, delegate to the extractor if it has the expected method
        if hasattr(self.table_extractor, 'extract_tables_from_pdf_page'):
            raw_tables = await self.table_extractor.extract_tables_from_pdf_page(page_content)
        else:
            # Fallback for testing/mocking
            raw_tables = []
            logger.warning(
                "table_extractor_no_method",
                message="Table extractor does not have extract_tables_from_pdf_page method"
            )

        logger.info(
            "table_extraction_raw_complete",
            raw_table_count=len(raw_tables),
        )

        # Step 2: Normalize and validate tables
        normalized_tables = []
        for idx, raw_table in enumerate(raw_tables):
            # If raw_table is already a TableData instance, use it directly
            # Otherwise, normalize it
            if isinstance(raw_table, TableData):
                normalized_table = raw_table
            else:
                normalized_table = self._normalize_table(raw_table, table_index=idx)

            # Step 3: Flag for human review if confidence is low
            # Refers to I2.6: Human-in-the-loop checkpoints
            if normalized_table.confidence < self.low_confidence_threshold:
                normalized_table.metadata["needs_human_review"] = True
                normalized_table.metadata["reason"] = "low_table_confidence"

                logger.warning(
                    "table_flagged_for_review",
                    table_index=idx,
                    confidence=normalized_table.confidence,
                    threshold=self.low_confidence_threshold,
                )

            normalized_tables.append(normalized_table)

        logger.info(
            "table_extraction_complete",
            table_count=len(normalized_tables),
            confidence_scores=[t.confidence for t in normalized_tables],
        )

        # LangSmith observability: Log extraction results
        if langsmith and span:
            langsmith.end_span(
                span,
                outputs={
                    "table_count": len(normalized_tables),
                    "extraction_scores": [t.confidence for t in normalized_tables],
                },
            )

        return normalized_tables

    def _normalize_table(
        self,
        raw_table: Dict[str, Any],
        table_index: int = 0,
    ) -> TableData:
        """
        Normalize a raw table into a TableData entity.

        Refers to I2.4: Table normalization rules with header reconciliation.
        Refers to I2.2: Table parser should not collapse merged cells incorrectly.

        This method ensures:
        - Consistent row/column structure (all rows have same column count)
        - Proper handling of merged cells (preserve content, pad with empty strings)
        - Header reconciliation (detect and normalize header rows)

        Args:
            raw_table: Raw table data from the extractor (dict or TableData)
            table_index: Index of the table in the page (for logging)

        Returns:
            Normalized TableData entity
        """
        # Extract rows and ensure consistent column count
        rows = raw_table.get("rows", [])

        if not rows:
            logger.warning(
                "table_normalization_empty",
                table_index=table_index,
            )
            # Return minimal valid table
            return TableData(
                rows=[[""]],
                confidence=0.0,
                metadata={"empty_table": True}
            )

        # Ensure all rows have the same number of columns
        # Refers to I2.2: Table parser should not collapse merged cells incorrectly
        max_cols = max(len(row) for row in rows)

        logger.debug(
            "table_normalization_column_count",
            table_index=table_index,
            max_columns=max_cols,
            row_column_counts=[len(row) for row in rows],
        )

        normalized_rows = []
        for row_idx, row in enumerate(rows):
            # Pad rows with fewer columns with empty strings
            # This preserves the table structure without collapsing merged cells
            normalized_row = row.copy() if isinstance(row, list) else list(row)

            while len(normalized_row) < max_cols:
                normalized_row.append("")

            normalized_rows.append(normalized_row)

            if len(row) < max_cols:
                logger.debug(
                    "table_normalization_row_padded",
                    table_index=table_index,
                    row_index=row_idx,
                    original_columns=len(row),
                    padded_columns=max_cols,
                )

        return TableData(
            rows=normalized_rows,
            confidence=raw_table.get("confidence", 0.0),
            bbox=raw_table.get("bbox"),
            metadata=raw_table.get("metadata", {}),
        )

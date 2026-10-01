"""#711: which deliveries may adopt a recovery-claimed processing authority."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from src.core.processing_authority import ProcessingAuthority, ProcessingStage
from src.core.tasks.ingestion_tasks import _authority_for_delivery


def _claimed() -> dict[str, object]:
    return ProcessingAuthority(
        tenant_id=uuid4(),
        document_id=uuid4(),
        revision_id=None,
        generation=3,
        stage=ProcessingStage.INGESTION,
        attempt_id=uuid4(),
        owner_token=uuid4(),
        fencing_token=7,
    ).to_message()


def test_first_execution_carries_the_claimed_authority() -> None:
    claimed = _claimed()
    task = SimpleNamespace(request=SimpleNamespace(retries=0))
    assert _authority_for_delivery(task, claimed) == claimed


def test_a_celery_retry_acquires_instead_of_readopting_a_released_grant() -> None:
    task = SimpleNamespace(request=SimpleNamespace(retries=1))
    assert _authority_for_delivery(task, _claimed()) is None


def test_authority_round_trips_through_a_task_message() -> None:
    claimed = _claimed()
    parsed = ProcessingAuthority.from_message(claimed)
    assert parsed is not None and parsed.to_message() == claimed
    assert ProcessingAuthority.from_message({"fencing_token": "x"}) is None
    assert ProcessingAuthority.from_message(None) is None

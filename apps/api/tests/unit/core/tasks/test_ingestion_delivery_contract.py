"""#711 RED/GREEN contract for Celery worker-loss delivery semantics."""
from __future__ import annotations

import ast
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[4]
INGESTION_TASKS = API_ROOT / "src" / "core" / "tasks" / "ingestion_tasks.py"


def _celery_task_options(function_name: str) -> dict[str, object]:
    module = ast.parse(INGESTION_TASKS.read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    task_decorator = next(
        decorator
        for decorator in function.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "task"
    )
    return {
        keyword.arg: ast.literal_eval(keyword.value)
        for keyword in task_decorator.keywords
        if keyword.arg is not None
        and isinstance(keyword.value, ast.Constant)
    }


def test_ingestion_redelivers_when_worker_process_is_lost() -> None:
    """Only idempotent ingestion earns late ACK / worker-loss redelivery."""
    options = _celery_task_options("process_document_async")

    assert options["acks_late"] is True
    assert options["reject_on_worker_lost"] is True

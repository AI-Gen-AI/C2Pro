from collections.abc import Callable
from typing import Any, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])

class _Celery:
    # Cover every attribute src uses (health checks read .control, dev
    # entrypoints use .conf/.start) — a missing name here becomes a hard
    # attr-defined error because this stub replaces the module for mypy.
    conf: Any
    control: Any
    def task(self, *args: Any, **kwargs: Any) -> Callable[[_F], Any]: ...
    def start(self, *args: Any, **kwargs: Any) -> Any: ...

celery_app: _Celery

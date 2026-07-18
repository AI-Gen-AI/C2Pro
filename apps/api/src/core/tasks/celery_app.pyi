from collections.abc import Callable
from typing import Any, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])

class _Celery:
    def task(self, *args: Any, **kwargs: Any) -> Callable[[_F], Any]: ...

celery_app: _Celery

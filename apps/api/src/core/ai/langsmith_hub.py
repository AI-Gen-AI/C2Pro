"""LangSmith Hub prompt resolution with environment isolation and fallback cache."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
    from langchain import hub
except ImportError:
    try:
        import langchain.hub as hub
    except ImportError:
        hub = SimpleNamespace(
            pull=lambda _handle: (_ for _ in ()).throw(RuntimeError("LangChain Hub unavailable"))
        )


@dataclass(frozen=True)
class LangSmithEnvProfile:
    """Resolved LANGCHAIN_* runtime profile for a specific deployment environment."""

    environment: str
    api_key: str | None
    project: str
    endpoint: str

    @classmethod
    def from_runtime_env(cls) -> LangSmithEnvProfile:
        environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        if environment in {"prod", "production"}:
            env_key = "PROD"
            normalized = "production"
            default_project = "c2pro-prod"
        elif environment == "staging":
            env_key = "STAGING"
            normalized = "staging"
            default_project = "c2pro-staging"
        else:
            env_key = "DEV"
            normalized = "development"
            default_project = "c2pro-dev"

        api_key = os.getenv(f"LANGCHAIN_API_KEY_{env_key}") or os.getenv("LANGCHAIN_API_KEY")
        project: str = (
            os.getenv(f"LANGCHAIN_PROJECT_{env_key}")
            or os.getenv("LANGCHAIN_PROJECT")
            or default_project
        )
        endpoint: str = (
            os.getenv(f"LANGCHAIN_ENDPOINT_{env_key}")
            or os.getenv("LANGCHAIN_ENDPOINT")
            or "https://api.smith.langchain.com"
        )
        return cls(environment=normalized, api_key=api_key, project=project, endpoint=endpoint)


class PromptHubResolver:
    """Fetch prompts from LangSmith Hub with timeout, A/B tags, and local cache fallback."""

    def __init__(
        self,
        *,
        cache_file: Path | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.cache_file = cache_file or Path(".cache/langsmith_prompt_cache.json")
        self._prompt_cache: dict[str, str] = self._load_cache()

    def resolve_prompt_tag(self, experiment_config: dict[str, Any] | None) -> str:
        if not experiment_config:
            return "latest"
        if not experiment_config.get("enabled", False):
            return str(experiment_config.get("fallback_tag", "latest"))
        if tag := experiment_config.get("prompt_tag"):
            return str(tag)
        if variant := experiment_config.get("variant"):
            return f"variant-{variant}"
        return str(experiment_config.get("active_tag", "latest"))

    def pull_prompt(
        self,
        *,
        prompt_repo: str,
        prompt_tag: str,
        fallback_prompt: str,
    ) -> tuple[str, str]:
        handle = f"{prompt_repo}:{prompt_tag}"

        profile = LangSmithEnvProfile.from_runtime_env()
        pull_kwargs: dict[str, Any] = {"api_url": profile.endpoint}
        if profile.api_key:
            pull_kwargs["api_key"] = profile.api_key

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                fetched = executor.submit(hub.pull, handle, **pull_kwargs).result(
                    timeout=self.timeout_seconds
                )
            prompt_text = self._coerce_prompt_text(fetched)
            self._prompt_cache[handle] = prompt_text
            self._persist_cache()
            return prompt_text, handle
        except (FuturesTimeoutError, Exception):
            if cached := self._prompt_cache.get(handle):
                return cached, f"cache:{handle}"
            return fallback_prompt, "fallback:local"

    def _coerce_prompt_text(self, prompt_obj: Any) -> str:
        if isinstance(prompt_obj, str):
            return prompt_obj
        template = getattr(prompt_obj, "template", None)
        if isinstance(template, str) and template.strip():
            return template
        messages = getattr(prompt_obj, "messages", None)
        if isinstance(messages, list):
            extracted: list[str] = []
            for message in messages:
                if isinstance(message, tuple) and len(message) == 2:
                    extracted.append(str(message[1]))
                    continue
                msg_prompt = getattr(message, "prompt", None)
                msg_template = getattr(msg_prompt, "template", None)
                if isinstance(msg_template, str):
                    extracted.append(msg_template)
            if extracted:
                return "\n\n".join(extracted)
        return str(prompt_obj)

    def _load_cache(self) -> dict[str, str]:
        if not self.cache_file.exists():
            return {}
        try:
            payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
        if isinstance(payload, dict):
            return {str(k): str(v) for k, v in payload.items()}
        return {}

    def _persist_cache(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(
                json.dumps(self._prompt_cache, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            return

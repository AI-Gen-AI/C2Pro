from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from anthropic import APIError, RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.ai.anthropic_wrapper import AIRequest as WrapperRequest
from src.core.ai.anthropic_wrapper import AnthropicWrapper, get_anthropic_wrapper
from src.core.ai.llm_client import LLMPartialGenerationError
from src.core.ai.model_capabilities import full_document_capacity
from src.core.ai.model_router import AITaskType
from src.core.ai.token_counter import get_token_counter
from src.core.database import get_session_with_tenant
from src.core.exceptions import AIServiceError

if TYPE_CHECKING:
    from src.core.ai.cost_controller import (
        BudgetExceededException,
        CostControllerService,
    )

logger = structlog.get_logger()


def _get_cost_controller() -> tuple[
    type[CostControllerService] | None, type[BudgetExceededException] | None
]:
    if os.getenv("C2PRO_TEST_LIGHT") == "1":
        return None, None
    from src.core.ai.cost_controller import (
        BudgetExceededException,
        CostControllerService,
    )

    return CostControllerService, BudgetExceededException


class AIService:
    """
    Orchestrator for AI calls with retry, parsing, and observability.
    """

    def __init__(
        self,
        wrapper: AnthropicWrapper | None = None,
        tenant_id: UUID | str | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        self.cost_controller: CostControllerService | None
        if os.getenv("C2PRO_AI_MOCK") == "1":
            self.wrapper = wrapper
        else:
            self.wrapper = wrapper or get_anthropic_wrapper()
        self.tenant_id = tenant_id
        self.db = db
        self._cost_controller_class, self._budget_exception = _get_cost_controller()
        if self.db and self._cost_controller_class:
            self.cost_controller = self._cost_controller_class(self.db)
        else:
            # In a real scenario, we might want to prevent the service from even starting
            # without a DB connection, but for now, we'll allow it and let it fail at runtime.
            self.cost_controller = None
            logger.warning(
                "AIService initialized without a database session. Cost control will be disabled."
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        reraise=True,
    )
    async def _call_wrapper(
        self,
        system_prompt: str,
        user_content: str,
        *,
        full_source_analysis: bool = False,
    ) -> Any:
        if self.wrapper is None:
            raise AIServiceError(message="AI client is not configured.")
        request = WrapperRequest(
            prompt=user_content,
            system_prompt=system_prompt,
            task_type=AITaskType.COMPLEX_EXTRACTION,
            tenant_id=self._tenant_uuid(),
            use_cache=not full_source_analysis,
            metadata={"full_source_analysis": full_source_analysis},
        )
        return await self.wrapper.generate(request)

    def _tenant_uuid(self) -> UUID | None:
        if self.tenant_id is None:
            return None
        return UUID(str(self.tenant_id))

    async def run_full_source_review(self, system_prompt: str, user_content: str) -> Any:
        """N12: review the entire N2-safe source with provider-native capacity."""
        return await self.run_extraction(system_prompt, user_content, full_source_analysis=True)

    async def run_extraction(
        self,
        system_prompt: str,
        user_content: str,
        *,
        full_source_analysis: bool = False,
    ) -> Any:
        """
        Runs an extraction with retries, robust JSON parsing, and usage logging.
        """
        start_time = time.perf_counter()
        if os.getenv("C2PRO_AI_MOCK") == "1":
            parsed = self._mock_extraction(system_prompt, user_content)
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "ai_usage_logged",
                timestamp=time.time(),
                model_used="mock",
                input_tokens=0,
                output_tokens=0,
                latency_ms=round(latency_ms, 2),
            )
            return parsed

        if not self.tenant_id:
            logger.error("Tenant ID missing, cannot proceed with AI call.")
            raise AIServiceError(message="El tenant no está configurado.")

        tenant_uuid = self._tenant_uuid()
        if tenant_uuid is None:
            raise AIServiceError(message="El tenant no está configurado.")

        if not self.cost_controller:
            if os.getenv("C2PRO_TEST_LIGHT") == "1":
                logger.warning("Cost controller disabled in light test mode.")
            else:
                logger.warning(
                    "cost_controller_deferred_to_tenant_session",
                    tenant_id=str(tenant_uuid),
                )

        # Full-source N12 preflight cannot authorize a possible 128k-token
        # response based on a fictitious one-cent estimate. Forecast one
        # provider-capacity call; actual usage is always tracked separately.
        estimated_cost = 0.01  # Legacy small calls keep their existing policy.
        try:
            async with get_session_with_tenant(tenant_uuid) as db_session:
                if self._cost_controller_class:
                    cost_controller = self._cost_controller_class(db_session)
                    if full_source_analysis:
                        if self.wrapper is None:
                            raise AIServiceError("AI client is not configured")
                        model = self.wrapper.model_router.select_model_with_budget_mode(
                            task_type=AITaskType.COMPLEX_EXTRACTION,
                            low_budget_mode=False,
                            input_token_estimate=len(user_content) // 4,
                        )
                        _, output_capacity = full_document_capacity(model.name)
                        estimate = get_token_counter().estimate_request(
                            model=model.name,
                            messages=[{"role": "user", "content": user_content}],
                            system=system_prompt,
                            max_tokens=output_capacity,
                        )
                        estimated_cost = cost_controller.calculate_cost(
                            model=model.name,
                            input_tokens=estimate.input_tokens,
                            output_tokens=output_capacity,
                        )
                        logger.info(
                            "n12_full_source_cost_preflight",
                            tenant_id=str(tenant_uuid),
                            model=model.name,
                            forecast_input_tokens=estimate.input_tokens,
                            reserved_output_capacity=output_capacity,
                            estimated_cost_usd=estimated_cost,
                        )
                    await cost_controller.check_budget_availability(tenant_uuid, estimated_cost)
        except Exception as exc:
            if self._budget_exception and isinstance(exc, self._budget_exception):
                raise AIServiceError(message=str(exc)) from exc
            if os.getenv("C2PRO_TEST_LIGHT") == "1" and self._budget_exception is None:
                logger.warning("budget_check_skipped_light_mode")
            else:
                logger.exception("budget_check_failed")
                # Fail-closed: If budget check fails for any reason, block the call.
                raise AIServiceError("Error al verificar el presupuesto.") from exc

        try:
            if full_source_analysis:
                response = await self._call_wrapper(
                    system_prompt, user_content, full_source_analysis=True
                )
            else:
                response = await self._call_wrapper(system_prompt, user_content)
        except LLMPartialGenerationError as exc:
            # A completed provider segment is billable even if continuation
            # failed and no valid N12 review can be used. Persist this usage.
            try:
                async with get_session_with_tenant(tenant_uuid) as db_session:
                    if self._cost_controller_class:
                        cost_controller = self._cost_controller_class(db_session)
                        actual_cost = cost_controller.calculate_cost(
                            model=exc.model,
                            input_tokens=exc.input_tokens,
                            output_tokens=exc.output_tokens,
                        )
                        await cost_controller.track_usage(tenant_uuid, actual_cost)
            except Exception:
                logger.exception(
                    "n12_partial_usage_persistence_failed",
                    tenant_id=str(tenant_uuid),
                    model=exc.model,
                    output_tokens=exc.output_tokens,
                    cost_usd=exc.cost_usd,
                )
            raise AIServiceError(
                message="Incomplete N12 provider output; billable partial usage recorded or flagged."
            ) from exc
        except RetryError as exc:
            raise AIServiceError(
                message="El servicio de IA está temporalmente no disponible."
            ) from exc
        except (RateLimitError, APIError) as exc:
            raise AIServiceError(
                message="El servicio de IA está temporalmente no disponible."
            ) from exc

        # After the call, track the actual usage
        try:
            async with get_session_with_tenant(tenant_uuid) as db_session:
                if self._cost_controller_class:
                    cost_controller = self._cost_controller_class(db_session)
                    actual_cost = cost_controller.calculate_cost(
                        model=response.model_used,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                    )
                    await cost_controller.track_usage(tenant_uuid, actual_cost)
        except Exception:
            if os.getenv("C2PRO_TEST_LIGHT") != "1":
                logger.exception("track_usage_failed")
            # If tracking fails, we log the error but don't fail the request,
            # as the user has already received the response.
            # This is a trade-off. We could also have a retry mechanism for tracking.

        # An output assembled from continuations must be ONE complete JSON
        # document; legacy repair could accept only the first JSON object.
        if getattr(response, "continuations", 0):
            try:
                parsed = json.loads(response.content)
            except json.JSONDecodeError as exc:
                raise AIServiceError(message="Continued AI output is incomplete JSON") from exc
        else:
            parsed = self._parse_json_response(response.content)

        latency_ms = response.latency_ms or (time.perf_counter() - start_time) * 1000
        logger.info(
            "ai_usage_logged",
            timestamp=time.time(),
            model_used=response.model_used,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=round(latency_ms, 2),
        )

        return parsed

    def _parse_json_response(self, raw: str) -> Any:
        raw = raw.strip()
        if not raw:
            raise AIServiceError(message="Failed to parse AI JSON response.")

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        repaired = self._try_json_repair(raw)
        if repaired is not None:
            return repaired

        candidate = self._extract_json_block(raw)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        repaired = self._try_json_repair(candidate)
        if repaired is not None:
            return repaired

        raise AIServiceError(message="Failed to parse AI JSON response.")

    def _try_json_repair(self, payload: str) -> Any | None:
        try:
            import json_repair
        except ImportError:
            return None

        try:
            if hasattr(json_repair, "loads"):
                return json_repair.loads(payload)
            if hasattr(json_repair, "repair_json"):
                repaired = json_repair.repair_json(payload)
                return json.loads(repaired)
        except Exception:
            return None

        return None

    def _extract_json_block(self, raw: str) -> str:
        start_idx = None
        stack: list[str] = []
        for i, ch in enumerate(raw):
            if ch in "{[":
                if start_idx is None:
                    start_idx = i
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]":
                if stack and ch == stack[-1]:
                    stack.pop()
                    if not stack and start_idx is not None:
                        return raw[start_idx : i + 1]

        first = min(
            (idx for idx in (raw.find("{"), raw.find("[")) if idx != -1),
            default=-1,
        )
        last = max(raw.rfind("}"), raw.rfind("]"))
        if first != -1 and last != -1 and last > first:
            return raw[first : last + 1]

        raise AIServiceError(message="No JSON block found in AI response.")

    def _mock_extraction(self, system_prompt: str, user_content: str) -> Any:  # noqa: ARG002
        prompt = system_prompt.lower()
        if "riesgo" in prompt or "risk" in prompt:
            return [
                {
                    "title": "Penalizacion por retraso",
                    "description": "El contrato menciona penalizaciones por demora en plazos.",
                    "severity": "medium",
                    "confidence": 0.86,
                }
            ]
        return [
            {
                "code": "1.1",
                "name": "Planificacion y permisos",
                "description": "Actividades iniciales del proyecto.",
                "item_type": "work_package",
                "confidence": 0.84,
            }
        ]

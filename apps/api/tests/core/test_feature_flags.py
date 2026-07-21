"""
C2Pro - Feature Flag Tests

Tests that feature flags actually control endpoint availability:
1. require_feature dependency blocks/allows requests based on settings
2. Router registration in create_application() respects feature flags
3. Feature flag state is logged at startup
"""

from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.config import settings
from src.core.middleware.feature_flags import require_feature

# ===========================================
# require_feature DEPENDENCY TESTS
# ===========================================


class TestRequireFeatureDependency:
    """Tests for the require_feature FastAPI dependency."""

    def _build_app(self, flag_name: str) -> FastAPI:
        app = FastAPI()

        @app.get("/gated", dependencies=[Depends(require_feature(flag_name))])
        async def gated():
            return {"status": "ok"}

        @app.get("/open")
        async def open_endpoint():
            return {"status": "ok"}

        return app

    def test_returns_404_when_flag_disabled(self):
        """Endpoint returns 404 when its feature flag is False."""
        app = self._build_app("feature_coherence_analysis")
        client = TestClient(app)

        with patch.object(settings, "feature_coherence_analysis", False):
            response = client.get("/gated")

        assert response.status_code == 404
        assert response.json()["detail"] == "Not Found"

    def test_passes_when_flag_enabled(self):
        """Endpoint returns 200 when its feature flag is True."""
        app = self._build_app("feature_coherence_analysis")
        client = TestClient(app)

        with patch.object(settings, "feature_coherence_analysis", True):
            response = client.get("/gated")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_unknown_flag_returns_404(self):
        """Unknown flag name defaults to disabled (404)."""
        app = self._build_app("feature_nonexistent")
        client = TestClient(app)

        response = client.get("/gated")
        assert response.status_code == 404

    def test_ungated_endpoint_always_works(self):
        """Endpoints without require_feature are unaffected."""
        app = self._build_app("feature_coherence_analysis")
        client = TestClient(app)

        with patch.object(settings, "feature_coherence_analysis", False):
            response = client.get("/open")

        assert response.status_code == 200

    def test_different_flags_independent(self):
        """Disabling one flag does not affect endpoints gated by another."""
        app = FastAPI()

        @app.get("/coherence", dependencies=[Depends(require_feature("feature_coherence_analysis"))])
        async def coherence():
            return {"feature": "coherence"}

        @app.get("/raci", dependencies=[Depends(require_feature("feature_raci_generation"))])
        async def raci():
            return {"feature": "raci"}

        client = TestClient(app)

        with patch.object(settings, "feature_coherence_analysis", True), \
             patch.object(settings, "feature_raci_generation", False):
            assert client.get("/coherence").status_code == 200
            assert client.get("/raci").status_code == 404


# ===========================================
# ROUTER REGISTRATION GATING TESTS
# ===========================================


class TestRouterRegistrationGating:
    """Tests that create_application() conditionally registers routers."""

    def _get_route_paths(self, app: FastAPI) -> set[str]:
        return set(app.openapi()["paths"].keys())

    def test_coherence_routers_registered_when_enabled(self):
        """Coherence routers registered when feature_coherence_analysis=True."""
        with patch.object(settings, "feature_coherence_analysis", True), \
             patch.object(settings, "feature_stakeholder_extraction", False), \
             patch.object(settings, "feature_raci_generation", False), \
             patch.object(settings, "feature_rfq_generation", False), \
             patch.object(settings, "feature_expediting_vision", False):
            from src.main import create_application
            app = create_application()

        paths = self._get_route_paths(app)
        coherence_paths = {p for p in paths if "/coherence" in p}
        assert len(coherence_paths) > 0, "Coherence routes should be registered"

    def test_coherence_routers_not_registered_when_disabled(self):
        """Coherence routers NOT registered when feature_coherence_analysis=False."""
        with patch.object(settings, "feature_coherence_analysis", False), \
             patch.object(settings, "feature_stakeholder_extraction", False), \
             patch.object(settings, "feature_raci_generation", False), \
             patch.object(settings, "feature_rfq_generation", False), \
             patch.object(settings, "feature_expediting_vision", False):
            from src.main import create_application
            app = create_application()

        paths = self._get_route_paths(app)
        coherence_paths = {p for p in paths if "/coherence" in p}
        assert len(coherence_paths) == 0, "Coherence routes should NOT be registered"

    def test_core_routers_always_registered(self):
        """Health, auth, projects, documents are always registered."""
        with patch.object(settings, "feature_coherence_analysis", False), \
             patch.object(settings, "feature_stakeholder_extraction", False), \
             patch.object(settings, "feature_raci_generation", False), \
             patch.object(settings, "feature_rfq_generation", False), \
             patch.object(settings, "feature_expediting_vision", False):
            from src.main import create_application
            app = create_application()

        paths = self._get_route_paths(app)
        # health_router has prefix="/health", so endpoint paths start with /health/
        assert any(p.startswith("/health") for p in paths), "Health route must always be registered"
        assert any("/auth" in p for p in paths), "Auth routes must always be registered"

    def test_stakeholder_routers_skipped_when_disabled(self):
        """Stakeholder routers skipped when feature_stakeholder_extraction=False."""
        with patch.object(settings, "feature_coherence_analysis", True), \
             patch.object(settings, "feature_stakeholder_extraction", False), \
             patch.object(settings, "feature_raci_generation", False), \
             patch.object(settings, "feature_rfq_generation", False), \
             patch.object(settings, "feature_expediting_vision", False):
            from src.main import create_application
            app = create_application()

        paths = self._get_route_paths(app)
        stakeholder_paths = {p for p in paths if "/stakeholders" in p}
        assert len(stakeholder_paths) == 0, "Stakeholder routes should NOT be registered"


# ===========================================
# FEATURE FLAG LOGGING TESTS
# ===========================================


class TestFeatureFlagLogging:
    """Tests that feature flag state is logged at startup."""

    def test_feature_flags_logged_at_startup(self):
        """create_application() logs feature flag values."""
        with patch.object(settings, "feature_coherence_analysis", True), \
             patch.object(settings, "feature_stakeholder_extraction", False), \
             patch.object(settings, "feature_raci_generation", False), \
             patch.object(settings, "feature_rfq_generation", False), \
             patch.object(settings, "feature_expediting_vision", False), \
             patch("src.main.logger") as mock_logger:
            from src.main import create_application
            create_application()

            feature_calls = [
                call for call in mock_logger.info.call_args_list
                if call[0] and call[0][0] == "feature_flags"
            ]
            assert len(feature_calls) >= 1, "Feature flags should be logged"
            kwargs = feature_calls[0][1]
            assert kwargs["coherence_analysis"] is True
            assert kwargs["raci_generation"] is False

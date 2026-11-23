"""The unauthenticated single-user API must never start as production."""

from __future__ import annotations

import pytest

from app.core.config import Settings, require_supported_runtime


@pytest.mark.parametrize("debug", [True, False])
def test_production_rejected_regardless_of_debug(debug: bool) -> None:
    settings = Settings(_env_file=None, environment="production", debug=debug)
    with pytest.raises(RuntimeError, match="authenticated sessions"):
        require_supported_runtime(settings)


@pytest.mark.parametrize("environment", ["development", "test"])
def test_supported_trusted_local_modes_unchanged(environment: str) -> None:
    settings = Settings(_env_file=None, environment=environment)
    assert require_supported_runtime(settings) is None

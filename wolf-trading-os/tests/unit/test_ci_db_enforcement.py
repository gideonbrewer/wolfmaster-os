"""WTOS_REQUIRE_DB behavior for the integration-test session (H5)."""

from __future__ import annotations

import pytest

from tests.integration.conftest import db_unreachable_action


class TestDbUnreachableAction:
    def test_flag_unset_allows_skip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WTOS_REQUIRE_DB", raising=False)
        assert db_unreachable_action() == "skip"

    def test_flag_set_forces_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WTOS_REQUIRE_DB", "1")
        assert db_unreachable_action() == "fail"

    def test_flag_other_value_allows_skip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WTOS_REQUIRE_DB", "0")
        assert db_unreachable_action() == "skip"

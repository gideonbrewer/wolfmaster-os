"""CLI argument handling and environment gating."""

from __future__ import annotations

import argparse

import pytest

from wolf_trading_os.cli import _cmd_database_reset_dev, _reset_refusal_reason, build_parser
from wolf_trading_os.config import Environment, Settings, get_settings


def _reset_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "yes": True,
        "force_unsafe_reset": False,
        "confirm_database": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestParser:
    def test_commands_exist(self) -> None:
        parser = build_parser()
        for argv in (
            ["import-option-alpha", "file.csv"],
            ["run-dashboard"],
            ["database-upgrade"],
            ["database-reset-dev", "--yes"],
        ):
            args = parser.parse_args(argv)
            assert args.command == argv[0]

    def test_import_accepts_multiple_files(self) -> None:
        args = build_parser().parse_args(["import-option-alpha", "a.csv", "b.csv"])
        assert len(args.files) == 2

    def test_no_order_commands(self) -> None:
        """The CLI surface must contain nothing order-related (AGENTS.md 13)."""
        parser = build_parser()
        subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        commands = set(subparsers.choices)
        assert commands == {
            "import-option-alpha",
            "run-dashboard",
            "database-upgrade",
            "database-reset-dev",
        }
        assert not any("order" in c or "trade" in c or "execute" in c for c in commands)


_DEV_URL = "postgresql+psycopg://wolf:secretpw@localhost:5432/wolf_trading_os_dev"


class TestResetGating:
    """M5: environment AND target-URL gating, with a double-confirmed override."""

    @pytest.fixture(autouse=True)
    def _dev_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WTOS_ENVIRONMENT", "development")
        monkeypatch.setattr(
            "wolf_trading_os.cli.get_settings",
            lambda: Settings(environment=Environment.DEVELOPMENT, database_url=_DEV_URL),
        )

    def test_dev_environment_local_dev_db_allowed(self) -> None:
        assert _reset_refusal_reason(_DEV_URL, _reset_args()) is None

    def test_docker_service_host_allowed(self) -> None:
        url = "postgresql+psycopg://wolf:pw@db:5432/wolf_trading_os_dev"
        assert _reset_refusal_reason(url, _reset_args()) is None

    def test_remote_host_refused(self) -> None:
        url = "postgresql+psycopg://wolf:pw@prod.example.com:5432/wolf_trading_os_dev"
        reason = _reset_refusal_reason(url, _reset_args())
        assert reason is not None and "not a local development host" in reason

    def test_non_dev_database_name_refused(self) -> None:
        url = "postgresql+psycopg://wolf:pw@localhost:5432/wolf_trading_os"
        reason = _reset_refusal_reason(url, _reset_args())
        assert reason is not None and "does not look like" in reason

    def test_malformed_url_refused(self) -> None:
        reason = _reset_refusal_reason("not a url at all ::", _reset_args())
        assert reason is not None and "malformed" in reason

    def test_missing_environment_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WTOS_ENVIRONMENT", raising=False)
        reason = _reset_refusal_reason(_DEV_URL, _reset_args())
        assert reason is not None and "EXPLICITLY" in reason

    def test_non_development_environment_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WTOS_ENVIRONMENT", "production")
        reason = _reset_refusal_reason(_DEV_URL, _reset_args())
        assert reason is not None

    def test_override_requires_exact_database_confirmation(self) -> None:
        url = "postgresql+psycopg://wolf:pw@remote.example.com:5432/shared"
        args = _reset_args(force_unsafe_reset=True, confirm_database="wrong")
        reason = _reset_refusal_reason(url, args)
        assert reason is not None and "--confirm-database 'shared'" in reason

    def test_override_with_exact_confirmation_allowed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = "postgresql+psycopg://wolf:secretpw@remote.example.com:5432/shared"
        args = _reset_args(force_unsafe_reset=True, confirm_database="shared")
        assert _reset_refusal_reason(url, args) is None
        echoed = capsys.readouterr().err
        assert "host=remote.example.com" in echoed and "database=shared" in echoed
        assert "secretpw" not in echoed  # passwords never logged

    def test_refusal_messages_never_contain_password(self) -> None:
        url = "postgresql+psycopg://wolf:secretpw@prod.example.com:5432/shared"
        reason = _reset_refusal_reason(url, _reset_args())
        assert reason is not None and "secretpw" not in reason

    @pytest.mark.parametrize(
        "environment",
        [Environment.TEST, Environment.STAGING, Environment.PRODUCTION],
    )
    def test_command_refused_outside_development(
        self, environment: Environment, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WTOS_ENVIRONMENT", environment.value)
        monkeypatch.setattr(
            "wolf_trading_os.cli.get_settings",
            lambda: Settings(environment=environment, database_url=_DEV_URL),
        )
        assert _cmd_database_reset_dev(_reset_args()) == 3

    def test_command_requires_confirmation_flag(self) -> None:
        assert _cmd_database_reset_dev(_reset_args(yes=False)) == 2

    def test_default_settings_cache_isolated(self) -> None:
        # sanity: the cached settings in tests run under WTOS_ENVIRONMENT=test
        assert get_settings().environment is Environment.TEST

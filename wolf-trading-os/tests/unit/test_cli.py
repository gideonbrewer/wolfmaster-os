"""CLI argument handling and environment gating."""

from __future__ import annotations

import argparse

import pytest

from wolf_trading_os.cli import _cmd_database_reset_dev, build_parser
from wolf_trading_os.config import Environment, Settings, get_settings


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


class TestResetGating:
    @pytest.mark.parametrize(
        "environment",
        [Environment.TEST, Environment.STAGING, Environment.PRODUCTION],
    )
    def test_reset_refused_outside_development(
        self, environment: Environment, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "wolf_trading_os.cli.get_settings",
            lambda: Settings(environment=environment),
        )
        exit_code = _cmd_database_reset_dev(argparse.Namespace(yes=True))
        assert exit_code == 3

    def test_reset_requires_confirmation_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "wolf_trading_os.cli.get_settings",
            lambda: Settings(environment=Environment.DEVELOPMENT),
        )
        exit_code = _cmd_database_reset_dev(argparse.Namespace(yes=False))
        assert exit_code == 2

    def test_default_settings_cache_isolated(self) -> None:
        # sanity: the cached settings in tests run under WTOS_ENVIRONMENT=test
        assert get_settings().environment is Environment.TEST

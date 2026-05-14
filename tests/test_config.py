"""Tests for shared application configuration."""

from __future__ import annotations

from src.twin.config import AppConfig


def test_app_config_prefers_explicit_initialization_timeout(monkeypatch) -> None:
    monkeypatch.setenv("INITIALIZATION_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("SCENARIO_TIMEOUT_SECONDS", "20")

    config = AppConfig()

    assert config.initialization_timeout_seconds == 45.0
    assert config.scenario_timeout_seconds == 20.0


def test_app_config_initialization_timeout_falls_back_to_scenario_timeout(monkeypatch) -> None:
    monkeypatch.delenv("INITIALIZATION_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("SCENARIO_TIMEOUT_SECONDS", "35")

    config = AppConfig()

    assert config.initialization_timeout_seconds == 35.0

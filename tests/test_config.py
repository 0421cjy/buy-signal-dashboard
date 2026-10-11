from __future__ import annotations

from app.config import DEFAULT_CONFIG, load_config


def test_missing_file_returns_defaults(tmp_path):
    cfg = load_config(tmp_path / "nope.yaml")
    assert cfg == DEFAULT_CONFIG
    assert cfg is not DEFAULT_CONFIG


def test_partial_file_overrides_only_given_keys(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("indicators:\n  vix:\n    strong_at_or_above: 35\n", encoding="utf-8")
    cfg = load_config(path)
    assert cfg["indicators"]["vix"]["strong_at_or_above"] == 35
    assert cfg["indicators"]["vix"]["signal_at_or_above"] == 25
    assert cfg["indicators"]["rsi"]["period"] == 14
    assert cfg["server"]["port"] == 8000


def test_empty_file_returns_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    assert load_config(path) == DEFAULT_CONFIG


def test_repo_config_matches_defaults():
    assert load_config() == DEFAULT_CONFIG

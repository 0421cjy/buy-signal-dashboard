from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

DEFAULT_CONFIG: dict = {
    "server": {"host": "127.0.0.1", "port": 8000, "open_browser": True},
    "cache_ttl_seconds": 600,
    "indicators": {
        "fear_greed": {"enabled": True, "strong_below": 20, "signal_below": 25},
        "vix": {"enabled": True, "strong_at_or_above": 30, "signal_at_or_above": 25},
        "market_mdd": {
            "enabled": True, "index": "^GSPC",
            "signal_at_or_below": -0.14, "strong_at_or_below": -0.30, "extreme_at_or_below": -0.47,
        },
        "rsi": {"enabled": True, "period": 14, "daily_at_or_below": 30, "weekly_at_or_below": 35},
        "mdd": {
            "enabled": True, "base_average": -0.14,
            "signal_at_or_below": -0.14, "strong_at_or_below": -0.30, "extreme_at_or_below": -0.47,
            "min_years": 3, "min_days_per_year": 200,
        },
        "moving_average": {"enabled": True, "daily_window": 200, "weekly_window": 200},
    },
}


def _merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Optional[Path] = None) -> dict:
    path = Path(path) if path is not None else CONFIG_PATH
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _merge(DEFAULT_CONFIG, data)

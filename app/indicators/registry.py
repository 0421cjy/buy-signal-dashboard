from __future__ import annotations

import importlib
import pkgutil
from typing import Callable, List, Optional

import pandas as pd

from app import indicators as _package
from app.indicators.base import EvalContext, Indicator, registered

_loaded = False


def _load_all() -> None:
    """app/indicators/ 안의 모든 지표 모듈을 import해서 @register가 실행되게 한다."""
    global _loaded
    if _loaded:
        return
    for module in pkgutil.iter_modules(_package.__path__):
        if module.name not in ("base", "registry"):
            importlib.import_module(f"{_package.__name__}.{module.name}")
    _loaded = True


def indicators_for(scope: str, indicators_cfg: dict) -> List[Indicator]:
    _load_all()
    chosen = [
        ind for ind in registered()
        if ind.scope == scope and indicators_cfg.get(ind.id, {}).get("enabled", True)
    ]
    return sorted(chosen, key=lambda ind: ind.order)


def evaluate_scope(
    scope: str,
    indicators_cfg: dict,
    get_daily: Callable[[str], pd.Series],
    get_fear_greed: Callable[[], dict],
    symbol: Optional[str] = None,
) -> List[dict]:
    results = []
    for ind in indicators_for(scope, indicators_cfg):
        ctx = EvalContext(
            config=indicators_cfg.get(ind.id, {}),
            get_daily=get_daily,
            get_fear_greed=get_fear_greed,
            symbol=symbol,
        )
        try:
            result = ind.evaluate(ctx)
        except Exception as exc:  # 지표 하나의 실패가 다른 지표에 번지지 않게 한다
            result = ind.failed(str(exc) or exc.__class__.__name__)
        results.append(result.to_dict())
    return results

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

STRONG = "strong_signal"
SIGNAL = "signal"
NEUTRAL = "neutral"
ERROR = "error"
INSUFFICIENT = "insufficient_data"

STATUS_TEXT = {STRONG: "강한 신호", SIGNAL: "신호", NEUTRAL: "중립", ERROR: "조회 실패", INSUFFICIENT: "데이터 부족"}
_RANK = {NEUTRAL: 0, SIGNAL: 1, STRONG: 2}


def strongest(*statuses: str) -> str:
    return max(statuses, key=lambda s: _RANK.get(s, -1))


@dataclass
class IndicatorResult:
    id: str
    name: str
    scope: str
    scored: bool
    status: str
    value: Optional[float] = None
    display: str = "—"
    label: str = ""
    threshold: str = ""
    as_of: Optional[str] = None
    details: Dict[str, str] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    thresholds: List[float] = field(default_factory=list)
    overlays: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvalContext:
    config: dict
    get_daily: Callable[[str], pd.Series]
    get_fear_greed: Callable[[], dict]
    symbol: Optional[str] = None


class Indicator:
    id: str = ""
    name: str = ""
    scope: str = "market"
    scored: bool = True
    order: int = 100

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        raise NotImplementedError

    def make(self, **fields: Any) -> IndicatorResult:
        return IndicatorResult(id=self.id, name=self.name, scope=self.scope, scored=self.scored, **fields)

    def failed(self, message: str) -> IndicatorResult:
        return self.make(status=ERROR, label="데이터를 가져오지 못했습니다", error=message)

    def insufficient(self, message: str) -> IndicatorResult:
        return self.make(status=INSUFFICIENT, label=message)


_REGISTRY: Dict[str, Indicator] = {}


def register(cls):
    _REGISTRY[cls.id] = cls()
    return cls


def registered() -> List[Indicator]:
    return list(_REGISTRY.values())


def to_points(s: pd.Series, years: int = 5, scale: float = 1.0) -> List[Dict[str, Any]]:
    s = s.dropna()
    if s.empty:
        return []
    s = s[s.index >= s.index[-1] - pd.DateOffset(years=years)]
    return [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v) * scale, 4)} for d, v in s.items()]


def as_of(s: pd.Series) -> str:
    return s.index[-1].strftime("%Y-%m-%d")


def fmt_pct(x: float) -> str:
    return f"{x * 100:+.1f}%"

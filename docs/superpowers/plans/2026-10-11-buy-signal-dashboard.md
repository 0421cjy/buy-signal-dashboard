# 매수 기준 대시보드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 5가지 매수 기준(공포·탐욕, VIX, RSI, 종목 MDD, 200일/200주 이평)을 판정하는 로컬 웹 대시보드를 만든다. 실행하면 시장 지표가 바로 표시되고, 티커를 검색하면 종목 지표가 추가된다.

**Architecture:** FastAPI 서버가 지표 플러그인(`app/indicators/*.py`, 자동 등록)을 평가해 JSON으로 반환하고, 빌드 없는 정적 HTML/JS 화면이 카드와 Chart.js 차트로 그린다. 데이터 계층(yfinance, CNN)은 `EvalContext`로 주입되므로 지표 로직은 네트워크 없이 테스트할 수 있다.

**Tech Stack:** Python 3.9+, FastAPI, uvicorn, yfinance, pandas, httpx, PyYAML, pytest, Chart.js 4.4.1 (cdnjs)

**Spec:** `docs/superpowers/specs/2026-10-11-buy-signal-dashboard-design.md`

## Global Constraints

- Python 3.9 호환: 모든 모듈 첫 줄에 `from __future__ import annotations`를 넣는다. 런타임에 평가되는 위치에서 `X | None`, `list[int]` 문법을 쓰지 않는다(`typing.Optional`, `List` 사용).
- 판정 상태 문자열: `strong_signal`, `signal`, `neutral`, `error`, `insufficient_data`
- 종합 점수: `scored: true`인 지표만 센다. 충족 = `signal` 또는 `strong_signal`. `error`/`insufficient_data`는 분모에서 빼고 실패 수로 따로 표시한다.
- 기본 임계값(config.yaml): 공포·탐욕 `<20` strong / `<25` signal, VIX `≥30` strong / `≥25` signal, RSI(14) 일봉 `≤30`·주봉 `≤35` 중 하나 해당 signal / 둘 다 해당 strong, 종목 MDD(52주=252거래일 최고 종가 대비) `≤−14%` signal / `≤−20%` strong, 이평 이격도 `<0` signal / `≤−5%` strong(200일·200주 중 더 강한 상태), S&P 500 MDD(사상 최고가 대비)는 참고용(`scored: false`)
- 서버는 `127.0.0.1:8000`에만 바인딩한다. 캐시 TTL 기본값은 600초다.
- 외부 요청: 타임아웃 10초, 실패 시 1회 재시도
- 사용자에게 보이는 문구는 한국어로 쓴다. `run.bat`의 출력 문구는 인코딩 문제를 피하려고 영어로 쓴다.
- 가격은 yfinance `auto_adjust=False`의 `Close`(분할만 반영된 종가, TradingView 기본 차트와 같음)를 쓴다.

## Review Focus

1. 티커 입력에 공백이나 소문자가 섞인 경우(`" aapl "`)에도 `AAPL`로 조회되어야 한다. → Task 6 `test_candidate_symbols_normalizes`
2. yfinance가 마지막 행에 NaN을 주거나 타임존이 붙은 인덱스를 주면, 지표 계산이 깨지지 않도록 정리해야 한다. → Task 6 `test_clean_close_drops_nan_and_timezone`
3. 티커를 조회하다 네트워크 오류가 나면 500이 아니라 502와 한국어 메시지를 반환해야 한다. → Task 7 `test_ticker_network_failure_returns_502`
4. 데이터 소스 하나(VIX)가 죽어도 나머지 시장 카드와 점수는 정상이어야 한다. → Task 7 `test_market_partial_failure`
5. 새로고침(`refresh=1`) 한 번에 같은 심볼을 여러 번 다시 받으면 Yahoo 요청 제한에 걸리므로, 요청당 심볼별로 한 번만 다시 받아야 한다. → Task 7 `test_refresh_refetches_each_symbol_once`

---

## File Structure

| 파일 | 책임 |
|---|---|
| `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore` | 의존성, 테스트 설정 |
| `config.yaml` | 사용자 수정용 설정 |
| `app/__init__.py`, `app/__main__.py` | 패키지, `python -m app` 진입점 |
| `app/config.py` | 기본값과 config.yaml 깊은 병합 |
| `app/data/cache.py` | TTL 메모리 캐시 |
| `app/data/prices.py` | yfinance 조회, 종가 정리, 티커 정규화와 해석 |
| `app/data/fear_greed.py` | CNN 공포·탐욕 조회와 파싱 |
| `app/indicators/base.py` | 상태 상수, `IndicatorResult`, `EvalContext`, `Indicator`, `register`, 공통 헬퍼 |
| `app/indicators/registry.py` | 지표 모듈 자동 import, scope별 조회, 안전한 평가 |
| `app/indicators/fear_greed.py`, `vix.py`, `market_mdd.py` | 시장 지표 |
| `app/indicators/rsi.py`, `mdd.py`, `moving_average.py` | 종목 지표 |
| `app/scoring.py` | 종합 점수 |
| `app/main.py` | FastAPI 앱 팩토리, API, `run()` |
| `static/index.html`, `static/style.css`, `static/app.js` | 화면 |
| `run.bat`, `run.sh`, `README.md` | 실행 스크립트, 문서 |
| `tests/…` | 테스트 |

---

### Task 1: 프로젝트 골격과 설정 로더

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `config.yaml`, `app/__init__.py`, `app/config.py`, `tests/__init__.py`, `tests/helpers.py`, `tests/test_config.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `app.config.DEFAULT_CONFIG: dict`, `app.config.load_config(path: Optional[Path] = None) -> dict`, `tests.helpers.series(values, start="2020-01-01") -> pd.Series` (영업일 인덱스)

- [ ] **Step 1: 의존성·설정 파일 작성**

`requirements.txt`:
```
fastapi>=0.110
uvicorn>=0.29
yfinance>=0.2.50
pandas>=2.0
httpx>=0.27
PyYAML>=6.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
addopts = -m "not live"
markers =
    live: 실제 네트워크를 사용하는 스모크 테스트 (pytest -m live)
```

`.gitignore` (전체 교체):
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

`config.yaml`:
```yaml
# 매수 기준 대시보드 설정 — 숫자만 바꿔서 자기 기준으로 쓰면 됩니다.
server:
  host: 127.0.0.1
  port: 8000
  open_browser: true

cache_ttl_seconds: 600

indicators:
  fear_greed:     { enabled: true, strong_below: 20, signal_below: 25 }
  vix:            { enabled: true, strong_at_or_above: 30, signal_at_or_above: 25 }
  market_mdd:     { enabled: true, index: "^GSPC", signal_at_or_below: -0.14, strong_at_or_below: -0.20 }
  rsi:            { enabled: true, period: 14, daily_at_or_below: 30, weekly_at_or_below: 35 }
  mdd:            { enabled: true, lookback_days: 252, signal_at_or_below: -0.14, strong_at_or_below: -0.20 }
  moving_average: { enabled: true, daily_window: 200, weekly_window: 200, strong_gap_at_or_below: -0.05 }
```

`app/__init__.py`와 `tests/__init__.py`는 빈 파일로 만든다.

`tests/helpers.py`:
```python
from __future__ import annotations

import pandas as pd


def series(values, start: str = "2020-01-01") -> pd.Series:
    """영업일 인덱스의 종가 시계열을 만든다."""
    values = list(values)
    index = pd.bdate_range(start=start, periods=len(values))
    return pd.Series([float(v) for v in values], index=index)
```

- [ ] **Step 2: 설치**

Run: `python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt` (macOS/Linux는 `.venv/bin/python`)
Expected: 오류 없이 설치 완료

- [ ] **Step 3: 실패하는 테스트 작성** — `tests/test_config.py`

```python
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
```

- [ ] **Step 4: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.config'`)

- [ ] **Step 5: 구현** — `app/config.py`

```python
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
        "market_mdd": {"enabled": True, "index": "^GSPC", "signal_at_or_below": -0.14, "strong_at_or_below": -0.20},
        "rsi": {"enabled": True, "period": 14, "daily_at_or_below": 30, "weekly_at_or_below": 35},
        "mdd": {"enabled": True, "lookback_days": 252, "signal_at_or_below": -0.14, "strong_at_or_below": -0.20},
        "moving_average": {"enabled": True, "daily_window": 200, "weekly_window": 200, "strong_gap_at_or_below": -0.05},
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
```

- [ ] **Step 6: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt requirements-dev.txt pytest.ini .gitignore config.yaml app tests
git commit -m "feat: 프로젝트 골격과 설정 로더"
```

---

### Task 2: TTL 메모리 캐시

**Files:**
- Create: `app/data/__init__.py` (빈 파일), `app/data/cache.py`, `tests/test_cache.py`

**Interfaces:**
- Produces: `TTLCache(ttl_seconds: float, clock: Callable[[], float] = time.monotonic)`, 메서드 `get_or_set(key: Hashable, factory: Callable[[], Any], refresh: bool = False) -> Any`. factory가 예외를 던지면 캐시에 저장하지 않고 그대로 전파한다.

- [ ] **Step 1: 실패하는 테스트** — `tests/test_cache.py`

```python
from __future__ import annotations

import pytest

from app.data.cache import TTLCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_caches_within_ttl_and_expires_after():
    clock = FakeClock()
    cache = TTLCache(10, clock=clock)
    calls = []

    def factory():
        calls.append(1)
        return len(calls)

    assert cache.get_or_set("k", factory) == 1
    clock.now = 9.9
    assert cache.get_or_set("k", factory) == 1
    clock.now = 10.0
    assert cache.get_or_set("k", factory) == 2


def test_refresh_bypasses_and_updates_cache():
    cache = TTLCache(100, clock=FakeClock())
    values = iter([1, 2])
    assert cache.get_or_set("k", lambda: next(values)) == 1
    assert cache.get_or_set("k", lambda: next(values), refresh=True) == 2
    assert cache.get_or_set("k", lambda: 99) == 2


def test_exceptions_are_not_cached():
    cache = TTLCache(100, clock=FakeClock())

    def boom():
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        cache.get_or_set("k", boom)
    assert cache.get_or_set("k", lambda: "ok") == "ok"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_cache.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현** — `app/data/cache.py`

```python
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Hashable, Tuple


class TTLCache:
    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl_seconds
        self._clock = clock
        self._store: Dict[Hashable, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Hashable, factory: Callable[[], Any], refresh: bool = False) -> Any:
        now = self._clock()
        if not refresh:
            with self._lock:
                hit = self._store.get(key)
            if hit is not None and now - hit[0] < self.ttl:
                return hit[1]
        value = factory()
        with self._lock:
            self._store[key] = (self._clock(), value)
        return value
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_cache.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add app/data tests/test_cache.py
git commit -m "feat: TTL 메모리 캐시"
```

---

### Task 3: 지표 기반 클래스, 레지스트리, 종합 점수

**Files:**
- Create: `app/indicators/__init__.py` (빈 파일), `app/indicators/base.py`, `app/indicators/registry.py`, `app/scoring.py`, `tests/test_registry.py`, `tests/test_scoring.py`

**Interfaces:**
- Produces (base):
  - 상수 `STRONG = "strong_signal"`, `SIGNAL = "signal"`, `NEUTRAL = "neutral"`, `ERROR = "error"`, `INSUFFICIENT = "insufficient_data"`, `STATUS_TEXT: Dict[str, str]`
  - `strongest(*statuses: str) -> str`: STRONG > SIGNAL > NEUTRAL 순으로 가장 강한 상태
  - `@dataclass IndicatorResult(id, name, scope, scored, status, value=None, display="—", label="", threshold="", as_of=None, details={}, history=[], thresholds=[], overlays={}, error=None)`, `.to_dict() -> dict`
  - `@dataclass EvalContext(config: dict, get_daily: Callable[[str], pd.Series], get_fear_greed: Callable[[], dict], symbol: Optional[str] = None)`
  - `class Indicator`: 클래스 속성 `id, name, scope ("market"|"ticker"), scored=True, order=100`, 메서드 `evaluate(ctx) -> IndicatorResult`, `make(**fields) -> IndicatorResult`, `failed(message) -> IndicatorResult`, `insufficient(message) -> IndicatorResult`
  - `register(cls)`: 클래스 데코레이터. 인스턴스를 전역 레지스트리에 넣는다.
  - `registered() -> List[Indicator]`
  - `to_points(s: pd.Series, years: int = 5, scale: float = 1.0) -> List[dict]`: `[{"date": "YYYY-MM-DD", "value": float}]`, NaN 제거, 소수 4자리 반올림
  - `as_of(s: pd.Series) -> str`, `fmt_pct(x: float) -> str` (예: `-0.162 → "-16.2%"`, `0.12 → "+12.0%"`)
- Produces (registry): `indicators_for(scope: str, indicators_cfg: dict) -> List[Indicator]` (order 순), `evaluate_scope(scope, indicators_cfg, get_daily, get_fear_greed, symbol=None) -> List[dict]` (예외는 `failed` 결과로 바꾼다)
- Produces (scoring): `score(results: List[dict]) -> dict` → `{"met", "strong", "total", "failed"}`

- [ ] **Step 1: 실패하는 테스트** — `tests/test_scoring.py`

```python
from __future__ import annotations

from app.scoring import score


def r(status, scored=True):
    return {"status": status, "scored": scored}


def test_counts_only_scored_and_evaluated():
    results = [
        r("strong_signal"),
        r("signal"),
        r("neutral"),
        r("error"),
        r("insufficient_data"),
        r("strong_signal", scored=False),
    ]
    assert score(results) == {"met": 2, "strong": 1, "total": 3, "failed": 2}


def test_empty():
    assert score([]) == {"met": 0, "strong": 0, "total": 0, "failed": 0}
```

`tests/test_registry.py`:
```python
from __future__ import annotations

import pandas as pd

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, ERROR, Indicator, fmt_pct, register, strongest, to_points,
)
from app.indicators.registry import evaluate_scope, indicators_for
from tests.helpers import series


@register
class _OkIndicator(Indicator):
    id = "_ok"
    name = "OK"
    scope = "_test"
    order = 2

    def evaluate(self, ctx):
        return self.make(status=NEUTRAL, value=float(ctx.config.get("x", 1)))


@register
class _BoomIndicator(Indicator):
    id = "_boom"
    name = "Boom"
    scope = "_test"
    order = 1

    def evaluate(self, ctx):
        ctx.get_daily("X")
        raise AssertionError("unreachable")


def _raise(_sym):
    raise RuntimeError("network down")


def test_indicators_for_filters_scope_order_and_enabled():
    ids = [i.id for i in indicators_for("_test", {})]
    assert ids == ["_boom", "_ok"]
    ids = [i.id for i in indicators_for("_test", {"_boom": {"enabled": False}})]
    assert ids == ["_ok"]


def test_evaluate_scope_isolates_failures_and_passes_config():
    results = evaluate_scope("_test", {"_ok": {"x": 7}}, get_daily=_raise, get_fear_greed=dict)
    by_id = {r["id"]: r for r in results}
    assert by_id["_boom"]["status"] == ERROR
    assert "network down" in by_id["_boom"]["error"]
    assert by_id["_ok"]["status"] == NEUTRAL
    assert by_id["_ok"]["value"] == 7.0
    assert by_id["_ok"]["scope"] == "_test"
    assert by_id["_ok"]["scored"] is True


def test_strongest():
    assert strongest(NEUTRAL, SIGNAL) == SIGNAL
    assert strongest(SIGNAL, STRONG, NEUTRAL) == STRONG
    assert strongest(NEUTRAL) == NEUTRAL


def test_to_points_trims_years_drops_nan_and_scales():
    s = series([1.0] * 1500)
    s.iloc[-2] = float("nan")
    points = to_points(s, years=1, scale=100)
    assert points[-1]["value"] == 100.0
    assert all(p["value"] == 100.0 for p in points)
    assert 250 <= len(points) <= 262
    assert points[0]["date"] >= (s.index[-1] - pd.DateOffset(years=1)).strftime("%Y-%m-%d")


def test_fmt_pct():
    assert fmt_pct(-0.162) == "-16.2%"
    assert fmt_pct(0.12) == "+12.0%"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_scoring.py tests/test_registry.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현** — `app/indicators/base.py`

```python
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
```

`app/indicators/registry.py`:
```python
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
```

`app/scoring.py`:
```python
from __future__ import annotations

from typing import List

from app.indicators.base import NEUTRAL, SIGNAL, STRONG

_EVALUATED = (STRONG, SIGNAL, NEUTRAL)


def score(results: List[dict]) -> dict:
    scored = [r for r in results if r["scored"]]
    evaluated = [r for r in scored if r["status"] in _EVALUATED]
    return {
        "met": sum(r["status"] in (STRONG, SIGNAL) for r in evaluated),
        "strong": sum(r["status"] == STRONG for r in evaluated),
        "total": len(evaluated),
        "failed": len(scored) - len(evaluated),
    }
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_scoring.py tests/test_registry.py -v`
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add app/indicators app/scoring.py tests/test_registry.py tests/test_scoring.py
git commit -m "feat: 지표 기반 클래스, 자동 등록 레지스트리, 종합 점수"
```

---

### Task 4: 시장 지표 — 공포·탐욕, VIX, S&P 500 MDD(참고)

**Files:**
- Create: `app/indicators/fear_greed.py`, `app/indicators/vix.py`, `app/indicators/market_mdd.py`, `tests/test_market_indicators.py`

**Interfaces:**
- Consumes: Task 3의 `Indicator`, `register`, 상수, `to_points`, `as_of`, `fmt_pct`
- Consumes: `ctx.get_fear_greed()`는 `{"score": float, "as_of": "YYYY-MM-DD", "history": [{"date", "value"}]}`를 반환한다(Task 6에서 구현).
- Produces: 지표 id `fear_greed`(order 10), `vix`(20), `market_mdd`(30, `scored=False`). 판정 함수 `fear_greed.grade(value, cfg) -> str`, `vix.grade(value, cfg) -> str`, `market_mdd.grade(drawdown, cfg) -> str`. `market_mdd.grade`는 Task 5의 종목 MDD에서도 재사용한다.

- [ ] **Step 1: 실패하는 테스트** — `tests/test_market_indicators.py`

```python
from __future__ import annotations

import pytest

from app.config import DEFAULT_CONFIG
from app.indicators import fear_greed, market_mdd, vix
from app.indicators.base import NEUTRAL, SIGNAL, STRONG, EvalContext
from tests.helpers import series

IND = DEFAULT_CONFIG["indicators"]


def ctx(cfg, daily=None, fg=None):
    return EvalContext(
        config=cfg,
        get_daily=lambda sym: daily[sym],
        get_fear_greed=lambda: fg,
    )


@pytest.mark.parametrize("value,expected", [(19.9, STRONG), (20, SIGNAL), (24.9, SIGNAL), (25, NEUTRAL)])
def test_fear_greed_grade(value, expected):
    assert fear_greed.grade(value, IND["fear_greed"]) == expected


def test_fear_greed_evaluate():
    fg = {"score": 17.0, "as_of": "2026-10-09", "history": [{"date": "2026-10-09", "value": 17.0}]}
    r = fear_greed.FearGreed().evaluate(ctx(IND["fear_greed"], fg=fg))
    assert r.status == STRONG
    assert r.value == 17.0
    assert r.display == "17"
    assert r.as_of == "2026-10-09"
    assert r.thresholds == [20, 25]
    assert r.label == "극단적 공포"


@pytest.mark.parametrize("value,expected", [(24.9, NEUTRAL), (25, SIGNAL), (29.9, SIGNAL), (30, STRONG)])
def test_vix_grade(value, expected):
    assert vix.grade(value, IND["vix"]) == expected


def test_vix_evaluate():
    r = vix.Vix().evaluate(ctx(IND["vix"], daily={"^VIX": series([15, 20, 32.14])}))
    assert r.status == STRONG
    assert r.display == "32.14"
    assert r.history[-1]["value"] == 32.14


@pytest.mark.parametrize(
    "dd,expected",
    [(-0.1399, NEUTRAL), (-0.14, SIGNAL), (-0.1999, SIGNAL), (-0.20, STRONG), (-0.30, STRONG), (-0.45, STRONG)],
)
def test_mdd_grade(dd, expected):
    assert market_mdd.grade(dd, IND["market_mdd"]) == expected


def test_market_mdd_uses_all_time_high_and_is_not_scored():
    s = series([100, 200, 150, 168])  # 사상 최고 200 대비 -16%
    r = market_mdd.MarketMdd().evaluate(ctx(IND["market_mdd"], daily={"^GSPC": s}))
    assert r.scored is False
    assert r.status == SIGNAL
    assert r.value == pytest.approx(-0.16)
    assert r.display == "-16.0%"
    assert r.history[-1]["value"] == pytest.approx(-16.0)
    assert r.thresholds == [-14.0, -20.0]
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_market_indicators.py -v`
Expected: FAIL (`ImportError: cannot import name 'fear_greed'`)

- [ ] **Step 3: 구현**

`app/indicators/fear_greed.py`:
```python
from __future__ import annotations

from app.indicators.base import NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, register

_LABELS = {STRONG: "극단적 공포", SIGNAL: "공포", NEUTRAL: "공포 구간 아님"}


def grade(value: float, cfg: dict) -> str:
    if value < cfg["strong_below"]:
        return STRONG
    if value < cfg["signal_below"]:
        return SIGNAL
    return NEUTRAL


@register
class FearGreed(Indicator):
    id = "fear_greed"
    name = "공포·탐욕 지수"
    scope = "market"
    order = 10

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        data = ctx.get_fear_greed()
        value = float(data["score"])
        status = grade(value, cfg)
        return self.make(
            status=status,
            value=value,
            display=f"{value:.0f}",
            label=_LABELS[status],
            threshold=f"{cfg['strong_below']} 미만 강한 신호 · {cfg['signal_below']} 미만 신호",
            as_of=data.get("as_of"),
            history=data.get("history", []),
            thresholds=[cfg["strong_below"], cfg["signal_below"]],
        )
```

`app/indicators/vix.py`:
```python
from __future__ import annotations

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, register, to_points,
)

_LABELS = {STRONG: "시장 패닉", SIGNAL: "불안 확대", NEUTRAL: "안정"}


def grade(value: float, cfg: dict) -> str:
    if value >= cfg["strong_at_or_above"]:
        return STRONG
    if value >= cfg["signal_at_or_above"]:
        return SIGNAL
    return NEUTRAL


@register
class Vix(Indicator):
    id = "vix"
    name = "VIX"
    scope = "market"
    order = 20

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        s = ctx.get_daily("^VIX").dropna()
        if s.empty:
            return self.insufficient("VIX 데이터가 없습니다")
        value = float(s.iloc[-1])
        status = grade(value, cfg)
        return self.make(
            status=status,
            value=value,
            display=f"{value:.2f}",
            label=_LABELS[status],
            threshold=f"{cfg['strong_at_or_above']} 이상 강한 신호 · {cfg['signal_at_or_above']} 이상 신호",
            as_of=as_of(s),
            history=to_points(s),
            thresholds=[cfg["strong_at_or_above"], cfg["signal_at_or_above"]],
        )
```

`app/indicators/market_mdd.py`:
```python
from __future__ import annotations

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points,
)

LABELS = {STRONG: "비중 대폭 확대 구간", SIGNAL: "매수 시작 구간", NEUTRAL: "대기"}


def grade(drawdown: float, cfg: dict) -> str:
    if drawdown <= cfg["strong_at_or_below"]:
        return STRONG
    if drawdown <= cfg["signal_at_or_below"]:
        return SIGNAL
    return NEUTRAL


def threshold_text(cfg: dict) -> str:
    return (
        f"{cfg['signal_at_or_below'] * 100:.0f}% 이하 매수 시작 · "
        f"{cfg['strong_at_or_below'] * 100:.0f}% 이하 비중 확대"
    )


def threshold_lines(cfg: dict) -> list:
    return [round(cfg["signal_at_or_below"] * 100, 4), round(cfg["strong_at_or_below"] * 100, 4)]


@register
class MarketMdd(Indicator):
    id = "market_mdd"
    name = "S&P 500 MDD (참고)"
    scope = "market"
    scored = False
    order = 30

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        s = ctx.get_daily(cfg["index"]).dropna()
        if s.empty:
            return self.insufficient("지수 데이터가 없습니다")
        drawdown = s / s.cummax() - 1
        value = float(drawdown.iloc[-1])
        status = grade(value, cfg)
        return self.make(
            status=status,
            value=value,
            display=fmt_pct(value),
            label=f"사상 최고가 대비 · {LABELS[status]}",
            threshold=threshold_text(cfg),
            as_of=as_of(s),
            history=to_points(drawdown, scale=100),
            thresholds=threshold_lines(cfg),
        )
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_market_indicators.py -v`
Expected: 모두 passed

- [ ] **Step 5: 커밋**

```bash
git add app/indicators/fear_greed.py app/indicators/vix.py app/indicators/market_mdd.py tests/test_market_indicators.py
git commit -m "feat: 시장 지표 (공포·탐욕, VIX, S&P 500 MDD 참고)"
```

---

### Task 5: 종목 지표 — RSI, 종목 MDD(52주), 200일/200주 이동평균

**Files:**
- Create: `app/indicators/rsi.py`, `app/indicators/mdd.py`, `app/indicators/moving_average.py`, `tests/test_ticker_indicators.py`

**Interfaces:**
- Consumes: Task 3의 base, Task 4의 `market_mdd.grade`, `market_mdd.LABELS`, `market_mdd.threshold_text`, `market_mdd.threshold_lines`
- Consumes: `ctx.symbol`은 이미 정규화된 심볼이고, `ctx.get_daily(symbol)`은 전체 이력 일봉 종가다.
- Produces: 지표 id `rsi`(order 40), `mdd`(50), `moving_average`(60). 함수 `rsi.wilder_rsi(s: pd.Series, period: int) -> pd.Series`, `rsi.grade(daily: float, weekly: Optional[float], cfg) -> str`, `moving_average.grade_gap(gap: float, cfg) -> str`, `moving_average.to_weekly(s) -> pd.Series`(W-FRI 마지막 값)

- [ ] **Step 1: 실패하는 테스트** — `tests/test_ticker_indicators.py`

```python
from __future__ import annotations

import pytest

from app.config import DEFAULT_CONFIG
from app.indicators import mdd, moving_average, rsi
from app.indicators.base import INSUFFICIENT, NEUTRAL, SIGNAL, STRONG, EvalContext
from tests.helpers import series

IND = DEFAULT_CONFIG["indicators"]


def ctx(cfg, s, symbol="TEST"):
    return EvalContext(config=cfg, get_daily=lambda sym: s, get_fear_greed=dict, symbol=symbol)


# --- RSI ---------------------------------------------------------------

def test_wilder_rsi_extremes():
    up = rsi.wilder_rsi(series(range(1, 60)), 14)
    down = rsi.wilder_rsi(series(range(60, 1, -1)), 14)
    assert up.iloc[-1] == pytest.approx(100.0)
    assert down.iloc[-1] == pytest.approx(0.0)


def test_wilder_rsi_balanced_is_50():
    values = [100 + (i % 2) for i in range(200)]
    assert rsi.wilder_rsi(series(values), 14).iloc[-1] == pytest.approx(50.0, abs=2.0)


@pytest.mark.parametrize(
    "daily,weekly,expected",
    [(30, 35, STRONG), (30, 35.1, SIGNAL), (30.1, 35, SIGNAL), (30.1, 35.1, NEUTRAL), (25, None, SIGNAL), (31, None, NEUTRAL)],
)
def test_rsi_grade(daily, weekly, expected):
    assert rsi.grade(daily, weekly, IND["rsi"]) == expected


def test_rsi_evaluate_both_oversold_is_strong():
    s = series(list(range(300, 100, -1)))  # 200거래일 하락 → 일봉·주봉 모두 0 근처
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], s))
    assert r.status == STRONG
    assert r.details["일봉 RSI(14)"].endswith("(해당)")
    assert r.details["주봉 RSI(14)"].endswith("(해당)")
    assert r.thresholds == [30, 35]
    assert "주봉 RSI" in r.overlays


def test_rsi_evaluate_only_weekly_oversold_is_signal():
    s = series(list(range(300, 100, -1)) + [103, 106, 109, 112, 115])  # 긴 하락 후 5일 반등
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], s))
    assert r.details["일봉 RSI(14)"].endswith("(미해당)")
    assert r.details["주봉 RSI(14)"].endswith("(해당)")
    assert r.status == SIGNAL


def test_rsi_weekly_insufficient_uses_daily_only():
    s = series(list(range(100, 60, -1)))  # 40거래일 = 약 8주, 주봉 RSI 계산 불가
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], s))
    assert r.details["주봉 RSI(14)"] == "데이터 부족"
    assert r.status == SIGNAL


def test_rsi_insufficient_data():
    r = rsi.Rsi().evaluate(ctx(IND["rsi"], series([1, 2, 3, 4, 5])))
    assert r.status == INSUFFICIENT


# --- 종목 MDD (52주) ----------------------------------------------------

def test_ticker_mdd_uses_52_week_high_not_all_time_high():
    values = [200] * 50 + [100] * 300 + [85]  # 사상 최고 200, 최근 252일 최고 100
    r = mdd.Mdd().evaluate(ctx(IND["mdd"], series(values)))
    assert r.scored is True
    assert r.value == pytest.approx(-0.15)
    assert r.status == SIGNAL
    assert r.details["사상 최고가 대비"] == "-57.5%"
    assert r.thresholds == [-14.0, -20.0]


def test_ticker_mdd_short_history_uses_available_high():
    r = mdd.Mdd().evaluate(ctx(IND["mdd"], series([100, 120, 90])))
    assert r.value == pytest.approx(-0.25)
    assert r.status == STRONG


# --- 이동평균 -----------------------------------------------------------

@pytest.mark.parametrize("gap,expected", [(0.0, NEUTRAL), (0.02, NEUTRAL), (-0.001, SIGNAL), (-0.049, SIGNAL), (-0.05, STRONG), (-0.2, STRONG)])
def test_grade_gap(gap, expected):
    assert moving_average.grade_gap(gap, IND["moving_average"]) == expected


def test_ma_both_available_signal():
    s = series([100] * 1100 + [97])  # 200일·200주 모두 약 -3%
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s))
    assert r.status == SIGNAL
    assert r.details["200일 이격도"].startswith("-3.0%")
    assert r.details["200주 이격도"].startswith("-3.0%")
    assert set(r.overlays) == {"200일선", "200주선"}


def test_ma_strong_when_5pct_below():
    s = series([100] * 1100 + [90])
    assert moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s)).status == STRONG


def test_ma_takes_strongest_of_daily_and_weekly():
    # 오래 200 → 최근 300일 100: 200일선 약 100(이격 -2%), 200주선은 100보다 훨씬 위(이격 -5% 이하)
    s = series([200] * 900 + [100] * 300 + [98])
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s))
    assert r.details["200일 이격도"].endswith("(신호)")
    assert r.details["200주 이격도"].endswith("(강한 신호)")
    assert r.status == STRONG


def test_ma_above_both_neutral():
    s = series([100] * 1100 + [110])
    assert moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s)).status == NEUTRAL


def test_ma_weekly_insufficient_uses_daily_only():
    s = series([100] * 300 + [97])
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], s))
    assert r.status == SIGNAL
    assert r.details["200주 이격도"] == "데이터 부족"
    assert set(r.overlays) == {"200일선"}


def test_ma_daily_insufficient():
    r = moving_average.MovingAverage().evaluate(ctx(IND["moving_average"], series([100] * 150)))
    assert r.status == INSUFFICIENT
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_ticker_indicators.py -v`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: 구현**

`app/indicators/rsi.py`:
```python
from __future__ import annotations

from typing import Optional

import pandas as pd

from app.indicators.base import (
    NEUTRAL, SIGNAL, STRONG, EvalContext, Indicator, IndicatorResult, as_of, register, to_points,
)
from app.indicators.moving_average import to_weekly

_LABELS = {STRONG: "일봉·주봉 모두 과매도", SIGNAL: "일봉·주봉 중 하나 과매도", NEUTRAL: "과매도 아님"}


def wilder_rsi(s: pd.Series, period: int) -> pd.Series:
    """Wilder 평활 RSI (TradingView ta.rsi와 같은 방식)."""
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return out.where(avg_gain.notna())


def grade(daily: float, weekly: Optional[float], cfg: dict) -> str:
    hits = int(daily <= cfg["daily_at_or_below"])
    if weekly is not None:
        hits += int(weekly <= cfg["weekly_at_or_below"])
    if hits == 2:
        return STRONG
    if hits == 1:
        return SIGNAL
    return NEUTRAL


def _mark(value: float, limit: float) -> str:
    return f"{value:.1f} ({'해당' if value <= limit else '미해당'})"


@register
class Rsi(Indicator):
    id = "rsi"
    name = "RSI (14, 일봉·주봉)"
    scope = "ticker"
    order = 40

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        period = int(cfg["period"])
        d_limit, w_limit = cfg["daily_at_or_below"], cfg["weekly_at_or_below"]
        s = ctx.get_daily(ctx.symbol).dropna()
        if len(s) <= period + 1:
            return self.insufficient(f"RSI 계산에 {period + 2}거래일 이상 필요합니다")

        daily = wilder_rsi(s, period).dropna()
        d = float(daily.iloc[-1])
        weekly = wilder_rsi(to_weekly(s), period).dropna()
        w = float(weekly.iloc[-1]) if not weekly.empty else None
        status = grade(d, w, cfg)

        details = {
            f"일봉 RSI({period})": _mark(d, d_limit),
            f"주봉 RSI({period})": _mark(w, w_limit) if w is not None else "데이터 부족",
        }
        overlays = {"주봉 RSI": to_points(weekly.reindex(daily.index, method="ffill"))} if w is not None else {}
        return self.make(
            status=status,
            value=d,
            display=f"일 {d:.1f} · 주 {w:.1f}" if w is not None else f"일 {d:.1f}",
            label=_LABELS[status],
            threshold=f"일봉 {d_limit} 이하 · 주봉 {w_limit} 이하 — 하나 해당 신호, 둘 다 해당 강한 신호",
            as_of=as_of(s),
            details=details,
            history=to_points(daily),
            overlays=overlays,
            thresholds=[d_limit, w_limit],
        )
```

`app/indicators/moving_average.py`:
```python
from __future__ import annotations

from typing import Optional

import pandas as pd

from app.indicators.base import (
    NEUTRAL, SIGNAL, STATUS_TEXT, STRONG, EvalContext, Indicator, IndicatorResult,
    as_of, fmt_pct, register, strongest, to_points,
)

_LABELS = {STRONG: "장기 이평선 아래로 크게 이탈", SIGNAL: "장기 이평선 아래", NEUTRAL: "장기 이평선 위"}


def to_weekly(s: pd.Series) -> pd.Series:
    return s.resample("W-FRI").last().dropna()


def grade_gap(gap: float, cfg: dict) -> str:
    if gap <= cfg["strong_gap_at_or_below"]:
        return STRONG
    if gap < 0:
        return SIGNAL
    return NEUTRAL


def _gap(price: float, sma: pd.Series) -> Optional[float]:
    last = sma.dropna()
    if last.empty:
        return None
    return price / float(last.iloc[-1]) - 1


@register
class MovingAverage(Indicator):
    id = "moving_average"
    name = "200일 / 200주 이동평균"
    scope = "ticker"
    order = 60

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        dw, ww = int(cfg["daily_window"]), int(cfg["weekly_window"])
        s = ctx.get_daily(ctx.symbol).dropna()
        if len(s) < dw:
            return self.insufficient(f"{dw}일 이동평균 계산에 데이터가 부족합니다")
        price = float(s.iloc[-1])
        daily_sma = s.rolling(dw).mean()
        weekly = to_weekly(s)
        weekly_sma = weekly.rolling(ww).mean() if len(weekly) >= ww else None

        gap_d = _gap(price, daily_sma)
        status_d = grade_gap(gap_d, cfg)
        details = {f"{dw}일 이격도": f"{fmt_pct(gap_d)} ({STATUS_TEXT[status_d]})"}
        overlays = {f"{dw}일선": to_points(daily_sma)}
        statuses = [status_d]

        if weekly_sma is not None:
            gap_w = _gap(price, weekly_sma)
            status_w = grade_gap(gap_w, cfg)
            statuses.append(status_w)
            details[f"{ww}주 이격도"] = f"{fmt_pct(gap_w)} ({STATUS_TEXT[status_w]})"
            overlays[f"{ww}주선"] = to_points(weekly_sma.reindex(s.index, method="ffill"))
        else:
            details[f"{ww}주 이격도"] = "데이터 부족"

        status = strongest(*statuses)
        return self.make(
            status=status,
            value=gap_d,
            display=fmt_pct(gap_d),
            label=_LABELS[status],
            threshold=f"이평선 아래 신호 · {cfg['strong_gap_at_or_below'] * 100:.0f}% 이상 이탈 강한 신호",
            as_of=as_of(s),
            details=details,
            history=to_points(s),
            overlays=overlays,
        )
```

`app/indicators/mdd.py`:
```python
from __future__ import annotations

from app.indicators.base import EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points
from app.indicators.market_mdd import LABELS, grade, threshold_lines, threshold_text


@register
class Mdd(Indicator):
    id = "mdd"
    name = "MDD (52주 고점 대비)"
    scope = "ticker"
    order = 50

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        lookback = int(cfg["lookback_days"])
        s = ctx.get_daily(ctx.symbol).dropna()
        if s.empty:
            return self.insufficient("가격 데이터가 없습니다")
        drawdown = s / s.rolling(lookback, min_periods=1).max() - 1
        value = float(drawdown.iloc[-1])
        status = grade(value, cfg)
        ath = float(s.iloc[-1] / s.max() - 1)
        return self.make(
            status=status,
            value=value,
            display=fmt_pct(value),
            label=LABELS[status],
            threshold=threshold_text(cfg),
            as_of=as_of(s),
            details={"사상 최고가 대비": fmt_pct(ath)},
            history=to_points(drawdown, scale=100),
            thresholds=threshold_lines(cfg),
        )
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_ticker_indicators.py -v`
Expected: 모두 passed

- [ ] **Step 5: 전체 테스트**

Run: `.venv/Scripts/python -m pytest -v`
Expected: 모두 passed

- [ ] **Step 6: 커밋**

```bash
git add app/indicators/rsi.py app/indicators/mdd.py app/indicators/moving_average.py tests/test_ticker_indicators.py
git commit -m "feat: 종목 지표 (RSI, 52주 MDD, 200일/200주 이동평균)"
```

---

### Task 6: 데이터 계층 — yfinance 가격, 티커 해석, CNN 공포·탐욕

**Files:**
- Create: `app/data/prices.py`, `app/data/fear_greed.py`, `tests/test_prices.py`, `tests/test_fear_greed_data.py`

**Interfaces:**
- Produces (prices):
  - `class TickerNotFound(Exception)`
  - `candidate_symbols(raw: str) -> List[str]`: 공백 제거와 대문자 변환. 6자리 숫자면 `[".KS", ".KQ"]` 후보, 빈 문자열이면 `TickerNotFound`
  - `clean_close(df: Optional[pd.DataFrame]) -> pd.Series`: `Close` 열에서 NaN을 빼고 타임존을 제거한 날짜 인덱스 시리즈. 비어 있으면 빈 Series
  - `fetch_history(symbol: str) -> pd.Series`: 전체 이력 일봉, 1회 재시도
  - `resolve_symbol(raw: str, get_daily: Callable[[str], pd.Series]) -> str`: 데이터가 있는 첫 후보. 없으면 `TickerNotFound`, 네트워크 예외는 그대로 전파
  - `fetch_name(symbol: str) -> str`: `shortName`, 실패하면 심볼
- Produces (fear_greed): `parse(payload: dict) -> dict`, `fetch_fear_greed() -> dict` (`{"score", "as_of", "history"}`)

- [ ] **Step 1: 실패하는 테스트** — `tests/test_prices.py`

```python
from __future__ import annotations

import pandas as pd
import pytest

from app.data.prices import TickerNotFound, candidate_symbols, clean_close, resolve_symbol
from tests.helpers import series


def test_candidate_symbols_normalizes():
    assert candidate_symbols(" aapl ") == ["AAPL"]
    assert candidate_symbols("brk-b") == ["BRK-B"]
    assert candidate_symbols("005930.ks") == ["005930.KS"]


def test_candidate_symbols_korean_code():
    assert candidate_symbols("005930") == ["005930.KS", "005930.KQ"]


def test_candidate_symbols_empty_raises():
    with pytest.raises(TickerNotFound):
        candidate_symbols("   ")


def test_clean_close_drops_nan_and_timezone():
    idx = pd.date_range("2026-01-05 09:30", periods=3, freq="D", tz="America/New_York")
    df = pd.DataFrame({"Close": [1.0, 2.0, float("nan")], "Open": [0, 0, 0]}, index=idx)
    s = clean_close(df)
    assert list(s.values) == [1.0, 2.0]
    assert s.index.tz is None
    assert s.index[0] == pd.Timestamp("2026-01-05")


def test_clean_close_empty():
    assert clean_close(None).empty
    assert clean_close(pd.DataFrame()).empty


def test_resolve_falls_back_to_kosdaq():
    data = {"035720.KS": pd.Series(dtype=float), "035720.KQ": series([1, 2])}
    assert resolve_symbol("035720", data.__getitem__) == "035720.KQ"


def test_resolve_not_found():
    with pytest.raises(TickerNotFound):
        resolve_symbol("ZZZZ", lambda sym: pd.Series(dtype=float))


def test_resolve_propagates_network_errors():
    def boom(sym):
        raise ConnectionError("offline")

    with pytest.raises(ConnectionError):
        resolve_symbol("AAPL", boom)
```

`tests/test_fear_greed_data.py`:
```python
from __future__ import annotations

from app.data.fear_greed import parse


def test_parse_cnn_payload():
    payload = {
        "fear_and_greed": {"score": 17.4286, "rating": "extreme fear", "timestamp": "2026-10-09T23:59:57+00:00"},
        "fear_and_greed_historical": {
            "data": [
                {"x": 1760054400000.0, "y": 30.0, "rating": "fear"},
                {"x": 1760140800000.0, "y": 17.4286, "rating": "extreme fear"},
            ]
        },
    }
    out = parse(payload)
    assert out["score"] == 17.4286
    assert out["as_of"] == "2026-10-09"
    assert out["history"] == [{"date": "2025-10-10", "value": 30.0}, {"date": "2025-10-11", "value": 17.4}]


def test_parse_without_history():
    out = parse({"fear_and_greed": {"score": 50, "timestamp": "2026-10-09T00:00:00+00:00"}})
    assert out["history"] == []
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_prices.py tests/test_fear_greed_data.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현**

`app/data/prices.py`:
```python
from __future__ import annotations

from typing import Callable, List, Optional

import pandas as pd

TIMEOUT_SECONDS = 10


class TickerNotFound(Exception):
    pass


def candidate_symbols(raw: str) -> List[str]:
    symbol = raw.strip().upper()
    if not symbol:
        raise TickerNotFound(raw)
    if len(symbol) == 6 and symbol.isdigit():
        return [f"{symbol}.KS", f"{symbol}.KQ"]
    return [symbol]


def clean_close(df: Optional[pd.DataFrame]) -> pd.Series:
    if df is None or df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    s = df["Close"].dropna().astype(float)
    index = pd.DatetimeIndex(s.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    s.index = index.normalize()
    return s[~s.index.duplicated(keep="last")]


def _with_retry(fn: Callable):
    try:
        return fn()
    except Exception:
        return fn()


def fetch_history(symbol: str) -> pd.Series:
    import yfinance as yf

    df = _with_retry(
        lambda: yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False, timeout=TIMEOUT_SECONDS)
    )
    return clean_close(df)


def resolve_symbol(raw: str, get_daily: Callable[[str], pd.Series]) -> str:
    for candidate in candidate_symbols(raw):
        if not get_daily(candidate).empty:
            return candidate
    raise TickerNotFound(raw.strip())


def fetch_name(symbol: str) -> str:
    try:
        import yfinance as yf

        info = yf.Ticker(symbol).info or {}
        return info.get("shortName") or info.get("longName") or symbol
    except Exception:
        return symbol
```

`app/data/fear_greed.py`:
```python
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://edition.cnn.com/",
}
TIMEOUT_SECONDS = 10
HISTORY_YEARS = 5


def parse(payload: dict) -> dict:
    current = payload["fear_and_greed"]
    points = payload.get("fear_and_greed_historical", {}).get("data", [])
    history = [
        {
            "date": datetime.fromtimestamp(p["x"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            "value": round(float(p["y"]), 1),
        }
        for p in points
    ]
    return {"score": float(current["score"]), "as_of": str(current["timestamp"])[:10], "history": history}


def fetch_fear_greed() -> dict:
    start = (date.today() - timedelta(days=365 * HISTORY_YEARS)).isoformat()
    url = URL.format(start=start)

    def get():
        resp = httpx.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()

    try:
        payload = get()
    except Exception:
        payload = get()
    return parse(payload)
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_prices.py tests/test_fear_greed_data.py -v`
Expected: 모두 passed

- [ ] **Step 5: 커밋**

```bash
git add app/data/prices.py app/data/fear_greed.py tests/test_prices.py tests/test_fear_greed_data.py
git commit -m "feat: 데이터 계층 (yfinance 가격·티커 해석, CNN 공포·탐욕)"
```

---

### Task 7: FastAPI 앱과 실행 진입점

**Files:**
- Create: `app/main.py`, `app/__main__.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `load_config`, `TTLCache`, `prices.fetch_history/resolve_symbol/fetch_name/TickerNotFound`, `fear_greed.fetch_fear_greed`, `evaluate_scope`, `score`
- Produces:
  - `create_app(config: Optional[dict] = None, fetch_daily=None, fetch_fear_greed=None, fetch_name=None) -> FastAPI`
  - `GET /api/health` → `{"status": "ok"}`
  - `GET /api/market?refresh=0|1` → `{"results": [IndicatorResult dict...], "score": {...}, "fetched_at": ISO 문자열}`
  - `GET /api/ticker/{symbol}?refresh=0|1` → `{"symbol", "name", "results", "fetched_at"}`. 404 `{"detail": "종목을 찾을 수 없습니다: X"}`, 502 `{"detail": "데이터 조회에 실패했습니다: ..."}`
  - `GET /` → `static/index.html`, `/static/*` → 정적 파일
  - `run() -> None`: config를 읽어 uvicorn을 실행하고 브라우저를 연다

- [ ] **Step 1: 실패하는 테스트** — `tests/test_api.py`

```python
from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_CONFIG
from app.main import create_app
from tests.helpers import series

FG = {"score": 15.0, "as_of": "2026-10-09", "history": []}
DATA = {
    "^VIX": series([20] * 50 + [31]),
    "^GSPC": series([100] * 50 + [85]),
    "AAPL": series([100] * 1100 + [90]),
    "123456.KQ": series([100] * 300 + [97]),
}


def make_client(daily=None, fg=None, calls=None):
    def fetch_daily(sym):
        if calls is not None:
            calls[sym] += 1
        if daily is not None:
            return daily(sym)
        return DATA.get(sym, pd.Series(dtype=float))

    app = create_app(
        config=DEFAULT_CONFIG,
        fetch_daily=fetch_daily,
        fetch_fear_greed=fg or (lambda: FG),
        fetch_name=lambda sym: f"Name of {sym}",
    )
    return TestClient(app)


def test_health():
    assert make_client().get("/api/health").json() == {"status": "ok"}


def test_market():
    body = make_client().get("/api/market").json()
    ids = [r["id"] for r in body["results"]]
    assert ids == ["fear_greed", "vix", "market_mdd"]
    assert body["score"] == {"met": 2, "strong": 2, "total": 2, "failed": 0}
    assert "fetched_at" in body


def test_market_partial_failure():
    def daily(sym):
        if sym == "^VIX":
            raise ConnectionError("yahoo down")
        return DATA[sym]

    body = make_client(daily=daily).get("/api/market").json()
    by_id = {r["id"]: r for r in body["results"]}
    assert by_id["vix"]["status"] == "error"
    assert by_id["fear_greed"]["status"] == "strong_signal"
    assert by_id["market_mdd"]["status"] == "signal"
    assert body["score"] == {"met": 1, "strong": 1, "total": 1, "failed": 1}


def test_ticker():
    body = make_client().get("/api/ticker/aapl").json()
    assert body["symbol"] == "AAPL"
    assert body["name"] == "Name of AAPL"
    assert [r["id"] for r in body["results"]] == ["rsi", "mdd", "moving_average"]


def test_ticker_korean_fallback():
    body = make_client().get("/api/ticker/123456").json()
    assert body["symbol"] == "123456.KQ"


def test_ticker_not_found():
    resp = make_client().get("/api/ticker/ZZZZ")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "종목을 찾을 수 없습니다: ZZZZ"


def test_ticker_network_failure_returns_502():
    def daily(sym):
        raise ConnectionError("offline")

    resp = make_client(daily=daily).get("/api/ticker/AAPL")
    assert resp.status_code == 502
    assert resp.json()["detail"].startswith("데이터 조회에 실패했습니다")


def test_cache_avoids_refetch():
    calls = Counter()
    client = make_client(calls=calls)
    client.get("/api/ticker/AAPL")
    client.get("/api/ticker/AAPL")
    assert calls["AAPL"] == 1


def test_refresh_refetches_each_symbol_once():
    calls = Counter()
    client = make_client(calls=calls)
    client.get("/api/ticker/AAPL")
    client.get("/api/ticker/AAPL?refresh=1")
    assert calls["AAPL"] == 2
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.main'`)

- [ ] **Step 3: 구현** — `app/main.py`

```python
from __future__ import annotations

import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Set

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.data import fear_greed, prices
from app.data.cache import TTLCache
from app.indicators.registry import evaluate_scope
from app.scoring import score

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(
    config: Optional[dict] = None,
    fetch_daily: Optional[Callable[[str], pd.Series]] = None,
    fetch_fear_greed: Optional[Callable[[], dict]] = None,
    fetch_name: Optional[Callable[[str], str]] = None,
) -> FastAPI:
    config = config or load_config()
    fetch_daily = fetch_daily or prices.fetch_history
    fetch_fear_greed = fetch_fear_greed or fear_greed.fetch_fear_greed
    fetch_name = fetch_name or prices.fetch_name
    cache = TTLCache(config["cache_ttl_seconds"])
    indicators_cfg = config["indicators"]

    app = FastAPI(title="매수 기준 대시보드")

    def getters(refresh: bool):
        refreshed: Set[tuple] = set()  # 한 요청 안에서는 같은 키를 한 번만 새로 받는다

        def cached(key, factory):
            force = refresh and key not in refreshed
            refreshed.add(key)
            return cache.get_or_set(key, factory, refresh=force)

        def get_daily(symbol: str) -> pd.Series:
            return cached(("daily", symbol), lambda: fetch_daily(symbol))

        def get_fear_greed() -> dict:
            return cached(("fear_greed",), fetch_fear_greed)

        def get_name(symbol: str) -> str:
            return cached(("name", symbol), lambda: fetch_name(symbol))

        return get_daily, get_fear_greed, get_name

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/market")
    def market(refresh: int = 0):
        get_daily, get_fg, _ = getters(bool(refresh))
        results = evaluate_scope("market", indicators_cfg, get_daily, get_fg)
        return {"results": results, "score": score(results), "fetched_at": datetime.now().isoformat(timespec="seconds")}

    @app.get("/api/ticker/{symbol}")
    def ticker(symbol: str, refresh: int = 0):
        get_daily, get_fg, get_name = getters(bool(refresh))
        try:
            resolved = prices.resolve_symbol(symbol, get_daily)
        except prices.TickerNotFound:
            raise HTTPException(status_code=404, detail=f"종목을 찾을 수 없습니다: {symbol.strip()}")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"데이터 조회에 실패했습니다: {exc}")
        results = evaluate_scope("ticker", indicators_cfg, get_daily, get_fg, symbol=resolved)
        return {
            "symbol": resolved,
            "name": get_name(resolved),
            "results": results,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")
    return app


def run() -> None:
    import uvicorn

    config = load_config()
    host, port = config["server"]["host"], int(config["server"]["port"])
    if config["server"].get("open_browser", True):
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(create_app(config), host=host, port=port)
```

`app/__main__.py`:
```python
from __future__ import annotations

from app.main import run

if __name__ == "__main__":
    run()
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest -v`
Expected: 모두 passed

- [ ] **Step 5: 커밋**

```bash
git add app/main.py app/__main__.py tests/test_api.py
git commit -m "feat: FastAPI 앱 (시장·종목 API, 캐시, 실행 진입점)"
```

---

### Task 8: 화면 (HTML/CSS/JS)

**Files:**
- Create: `static/index.html`, `static/style.css`, `static/app.js`, `tests/test_static.py`

**Interfaces:**
- Consumes: Task 7의 `/api/market`, `/api/ticker/{symbol}` 응답 형식, `IndicatorResult` 필드(`id, name, scored, status, display, label, threshold, as_of, details, history, thresholds, overlays, error`)

- [ ] **Step 1: 실패하는 테스트** — `tests/test_static.py`

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import DEFAULT_CONFIG
from app.main import create_app


def client():
    return TestClient(create_app(config=DEFAULT_CONFIG, fetch_daily=lambda s: None, fetch_fear_greed=dict, fetch_name=str))


def test_index_served():
    resp = client().get("/")
    assert resp.status_code == 200
    assert "매수 기준 체크" in resp.text
    assert "chart.umd.min.js" in resp.text


def test_assets_served():
    c = client()
    assert c.get("/static/app.js").status_code == 200
    assert c.get("/static/style.css").status_code == 200
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_static.py -v`
Expected: FAIL (index.html이 없어서 500 또는 404)

- [ ] **Step 3: `static/index.html` 작성**

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>매수 기준 체크</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
</head>
<body>
  <header class="top">
    <div class="title-row">
      <h1>매수 기준 체크</h1>
      <div class="meta">
        <span id="updated">불러오는 중…</span>
        <button id="refresh-btn" type="button" class="ghost">새로고침</button>
      </div>
    </div>
    <form id="search-form" autocomplete="off">
      <input id="ticker-input" placeholder="티커 입력 (AAPL, 005930)" aria-label="티커">
      <button type="submit">조회</button>
    </form>
    <p id="ticker-error" class="error-text" hidden></p>
    <div id="recent" class="chips"></div>
  </header>

  <main>
    <section id="summary" class="summary" aria-live="polite"></section>

    <section>
      <h2>시장 지표</h2>
      <div id="market-cards" class="cards"></div>
    </section>

    <section>
      <h2 id="ticker-title">종목 지표</h2>
      <div id="ticker-cards" class="cards">
        <p class="hint">티커를 검색하면 RSI, MDD(52주 고점 대비), 200일/200주 이동평균을 확인할 수 있습니다.</p>
      </div>
    </section>
  </main>

  <dialog id="detail">
    <div class="detail-head">
      <h3 id="detail-title"></h3>
      <div class="range">
        <button type="button" data-range="1y" class="active">1년</button>
        <button type="button" data-range="5y">5년</button>
      </div>
      <button type="button" id="detail-close" class="ghost" aria-label="닫기">✕</button>
    </div>
    <div class="detail-chart"><canvas id="detail-canvas"></canvas></div>
  </dialog>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: `static/style.css` 작성**

```css
:root {
  --bg: #f6f7f9;
  --surface: #ffffff;
  --text: #1b1f24;
  --muted: #5f6b7a;
  --border: #e2e6eb;
  --accent: #2f6fde;
  --line: #2f6fde;
  --overlay-1: #e08a1e;
  --overlay-2: #8a4fd6;
  --threshold: #9aa4b1;
  --strong: #1f9d55;
  --strong-bg: #e3f6eb;
  --signal: #b7791f;
  --signal-bg: #fdf3dc;
  --neutral: #5f6b7a;
  --neutral-bg: #eef1f4;
  --error: #c53030;
  --error-bg: #fde8e8;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111418;
    --surface: #1a1f25;
    --text: #e6e9ed;
    --muted: #96a1ae;
    --border: #2a313a;
    --accent: #6c9cf0;
    --line: #6c9cf0;
    --overlay-1: #f0a548;
    --overlay-2: #b08cf0;
    --threshold: #5d6875;
    --strong: #4ccf85;
    --strong-bg: #173527;
    --signal: #e8b54d;
    --signal-bg: #3a2f17;
    --neutral: #96a1ae;
    --neutral-bg: #232a32;
    --error: #f07878;
    --error-bg: #3a1c1c;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, "Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
  line-height: 1.45;
}
.top, main { max-width: 1120px; margin: 0 auto; padding: 16px; }
.title-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
h1 { font-size: 1.4rem; margin: 0; }
h2 { font-size: 1.05rem; margin: 24px 0 12px; color: var(--muted); font-weight: 600; }
.meta { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 0.9rem; }
#search-form { display: flex; gap: 8px; margin-top: 16px; }
#ticker-input {
  flex: 1; min-width: 0; padding: 10px 12px; font-size: 1rem;
  border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text);
}
button {
  padding: 10px 16px; font-size: 0.95rem; border-radius: 8px; border: 1px solid var(--accent);
  background: var(--accent); color: #fff; cursor: pointer;
}
button.ghost { background: transparent; color: var(--text); border-color: var(--border); padding: 6px 10px; }
.error-text { color: var(--error); margin: 8px 0 0; font-size: 0.9rem; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.chips button { padding: 4px 10px; font-size: 0.85rem; background: var(--surface); color: var(--text); border-color: var(--border); }
.summary {
  display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-radius: 12px;
  background: var(--surface); border: 1px solid var(--border); font-size: 1.05rem; font-weight: 600;
}
.dots { letter-spacing: 3px; color: var(--strong); font-size: 1.2rem; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
.card {
  background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--neutral);
  border-radius: 12px; padding: 14px 16px; cursor: pointer; display: flex; flex-direction: column; gap: 6px;
}
.card.strong { border-left-color: var(--strong); }
.card.signal { border-left-color: var(--signal); }
.card.error { border-left-color: var(--error); }
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.card-head h3 { margin: 0; font-size: 0.95rem; font-weight: 600; }
.badge { font-size: 0.78rem; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.badge.strong { color: var(--strong); background: var(--strong-bg); }
.badge.signal { color: var(--signal); background: var(--signal-bg); }
.badge.neutral { color: var(--neutral); background: var(--neutral-bg); }
.badge.error { color: var(--error); background: var(--error-bg); }
.tag { font-size: 0.72rem; color: var(--muted); border: 1px solid var(--border); border-radius: 4px; padding: 0 5px; margin-left: 6px; }
.value { font-size: 1.8rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.label { font-size: 0.92rem; }
.small { font-size: 0.8rem; color: var(--muted); }
.details { margin: 2px 0 0; display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; font-size: 0.85rem; }
.details dt { color: var(--muted); }
.details dd { margin: 0; font-variant-numeric: tabular-nums; }
.mini { height: 70px; position: relative; }
.hint { color: var(--muted); }
dialog {
  width: min(960px, calc(100vw - 32px)); border: 1px solid var(--border); border-radius: 14px;
  background: var(--surface); color: var(--text); padding: 16px;
}
dialog::backdrop { background: rgba(0, 0, 0, 0.45); }
.detail-head { display: flex; align-items: center; gap: 12px; }
.detail-head h3 { margin: 0; flex: 1; font-size: 1.05rem; }
.range button { padding: 4px 10px; background: transparent; color: var(--text); border-color: var(--border); }
.range button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.detail-chart { height: 420px; position: relative; margin-top: 12px; }
@media (max-width: 640px) {
  .cards { grid-template-columns: 1fr; }
  .detail-chart { height: 300px; }
}
```

- [ ] **Step 5: `static/app.js` 작성**

```js
"use strict";

const STATUS = {
  strong_signal: { text: "강한 신호", cls: "strong" },
  signal: { text: "신호", cls: "signal" },
  neutral: { text: "중립", cls: "neutral" },
  error: { text: "조회 실패", cls: "error" },
  insufficient_data: { text: "데이터 부족", cls: "error" },
};
const EVALUATED = ["strong_signal", "signal", "neutral"];
const RECENT_KEY = "buy-signal:recent";

const state = { market: [], ticker: [], tickerInfo: null, charts: {}, detail: null, detailResult: null, detailRange: "1y" };

const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

async function getJSON(url) {
  const res = await fetch(url);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

function computeScore(results) {
  const scored = results.filter((r) => r.scored);
  const evaluated = scored.filter((r) => EVALUATED.includes(r.status));
  return {
    met: evaluated.filter((r) => r.status !== "neutral").length,
    strong: evaluated.filter((r) => r.status === "strong_signal").length,
    total: evaluated.length,
    failed: scored.length - evaluated.length,
  };
}

function renderSummary() {
  const s = computeScore(state.market.concat(state.ticker));
  const box = $("summary");
  box.replaceChildren();
  const prefix = state.tickerInfo ? "" : "시장 ";
  let text = `${prefix}${s.met} / ${s.total} 충족 (강한 신호 ${s.strong})`;
  if (s.failed) text += ` · ${s.failed}개 조회 실패`;
  box.append(el("span", "dots", "●".repeat(s.met) + "○".repeat(Math.max(s.total - s.met, 0))), el("span", null, text));
}

function sliceRange(points, range) {
  if (range === "5y" || points.length === 0) return points;
  const last = new Date(points[points.length - 1].date);
  last.setFullYear(last.getFullYear() - 1);
  const cut = last.toISOString().slice(0, 10);
  return points.filter((p) => p.date >= cut);
}

function chartConfig(r, range, mini) {
  const points = sliceRange(r.history || [], range);
  const labels = points.map((p) => p.date);
  const datasets = [{
    label: r.name, data: points.map((p) => p.value),
    borderColor: css("--line"), borderWidth: mini ? 1.5 : 2, pointRadius: 0, tension: 0,
  }];
  const overlayColors = [css("--overlay-1"), css("--overlay-2")];
  Object.entries(r.overlays || {}).forEach(([name, ov], i) => {
    const map = new Map(ov.map((p) => [p.date, p.value]));
    datasets.push({
      label: name, data: labels.map((d) => (map.has(d) ? map.get(d) : null)),
      borderColor: overlayColors[i % overlayColors.length], borderWidth: 1.5, pointRadius: 0, spanGaps: true,
    });
  });
  (r.thresholds || []).forEach((t) => {
    datasets.push({
      label: `기준 ${t}`, data: labels.map(() => t),
      borderColor: css("--threshold"), borderDash: [4, 4], borderWidth: 1, pointRadius: 0,
    });
  });
  return {
    type: "line",
    data: { labels, datasets },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: !mini, labels: { color: css("--muted") } }, tooltip: { enabled: !mini } },
      scales: {
        x: { display: !mini, ticks: { maxTicksLimit: 8, color: css("--muted") }, grid: { color: css("--border") } },
        y: { display: !mini, ticks: { color: css("--muted") }, grid: { color: css("--border") } },
      },
    },
  };
}

function destroyCharts(containerId) {
  (state.charts[containerId] || []).forEach((c) => c.destroy());
  state.charts[containerId] = [];
}

function buildCard(r, containerId, onRetry) {
  const st = STATUS[r.status] || STATUS.neutral;
  const card = el("article", `card ${st.cls}`);

  const head = el("div", "card-head");
  const title = el("h3", null, r.name);
  if (!r.scored) title.append(el("span", "tag", "참고 · 점수 제외"));
  head.append(title, el("span", `badge ${st.cls}`, st.text));
  card.append(head);

  card.append(el("div", "value", r.display || "—"));
  if (r.label) card.append(el("div", "label", r.label));

  if (r.status === "error") {
    card.append(el("div", "small", r.error || ""));
    const retry = el("button", "ghost", "다시 시도");
    retry.type = "button";
    retry.addEventListener("click", (e) => { e.stopPropagation(); onRetry(); });
    card.append(retry);
    return card;
  }

  const entries = Object.entries(r.details || {});
  if (entries.length) {
    const dl = el("dl", "details");
    entries.forEach(([k, v]) => dl.append(el("dt", null, k), el("dd", null, v)));
    card.append(dl);
  }
  if (r.threshold) card.append(el("div", "small", `기준: ${r.threshold}`));
  if (r.as_of) card.append(el("div", "small", `데이터 기준일 ${r.as_of}`));

  if ((r.history || []).length && window.Chart) {
    const wrap = el("div", "mini");
    const canvas = el("canvas");
    wrap.append(canvas);
    card.append(wrap);
    requestAnimationFrame(() => {
      state.charts[containerId].push(new Chart(canvas, chartConfig(r, "1y", true)));
    });
    card.addEventListener("click", () => openDetail(r));
  }
  return card;
}

function renderCards(containerId, results, onRetry) {
  destroyCharts(containerId);
  const box = $(containerId);
  box.replaceChildren(...results.map((r) => buildCard(r, containerId, onRetry)));
}

function renderMessage(containerId, message) {
  destroyCharts(containerId);
  $(containerId).replaceChildren(el("p", "hint", message));
}

function setUpdated(iso) {
  const t = iso ? new Date(iso) : new Date();
  $("updated").textContent = `마지막 갱신 ${t.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}`;
}

async function loadMarket(refresh = false) {
  renderMessage("market-cards", "시장 지표를 불러오는 중…");
  try {
    const body = await getJSON(`/api/market${refresh ? "?refresh=1" : ""}`);
    state.market = body.results;
    renderCards("market-cards", state.market, () => loadMarket(true));
    setUpdated(body.fetched_at);
  } catch (err) {
    state.market = [];
    renderMessage("market-cards", `시장 지표를 불러오지 못했습니다: ${err.message}`);
  }
  renderSummary();
}

async function loadTicker(raw, refresh = false) {
  const symbol = raw.trim();
  if (!symbol) return;
  $("ticker-error").hidden = true;
  renderMessage("ticker-cards", `${symbol} 조회 중…`);
  try {
    const body = await getJSON(`/api/ticker/${encodeURIComponent(symbol)}${refresh ? "?refresh=1" : ""}`);
    state.ticker = body.results;
    state.tickerInfo = { symbol: body.symbol, name: body.name };
    $("ticker-title").textContent = `종목 지표 · ${body.name} (${body.symbol})`;
    renderCards("ticker-cards", state.ticker, () => loadTicker(body.symbol, true));
    rememberTicker(body.symbol);
    setUpdated(body.fetched_at);
  } catch (err) {
    $("ticker-error").textContent = err.message;
    $("ticker-error").hidden = false;
    if (!state.tickerInfo) {
      renderMessage("ticker-cards", "티커를 검색하면 RSI, MDD(52주 고점 대비), 200일/200주 이동평균을 확인할 수 있습니다.");
    } else {
      renderCards("ticker-cards", state.ticker, () => loadTicker(state.tickerInfo.symbol, true));
    }
  }
  renderSummary();
}

function readRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch { return []; }
}

function rememberTicker(symbol) {
  const list = [symbol, ...readRecent().filter((s) => s !== symbol)].slice(0, 5);
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch { /* 저장 불가 환경은 무시 */ }
  renderRecent();
}

function renderRecent() {
  const box = $("recent");
  box.replaceChildren(...readRecent().map((s) => {
    const b = el("button", null, s);
    b.type = "button";
    b.addEventListener("click", () => { $("ticker-input").value = s; loadTicker(s); });
    return b;
  }));
}

function openDetail(r) {
  state.detailResult = r;
  state.detailRange = "1y";
  $("detail-title").textContent = `${r.name} · ${r.display}`;
  document.querySelectorAll(".range button").forEach((b) => b.classList.toggle("active", b.dataset.range === "1y"));
  $("detail").showModal();
  drawDetail();
}

function drawDetail() {
  if (state.detail) state.detail.destroy();
  state.detail = new Chart($("detail-canvas"), chartConfig(state.detailResult, state.detailRange, false));
}

function init() {
  $("search-form").addEventListener("submit", (e) => { e.preventDefault(); loadTicker($("ticker-input").value); });
  $("refresh-btn").addEventListener("click", () => {
    loadMarket(true);
    if (state.tickerInfo) loadTicker(state.tickerInfo.symbol, true);
  });
  $("detail-close").addEventListener("click", () => $("detail").close());
  $("detail").addEventListener("click", (e) => { if (e.target === $("detail")) $("detail").close(); });
  document.querySelectorAll(".range button").forEach((b) => b.addEventListener("click", () => {
    state.detailRange = b.dataset.range;
    document.querySelectorAll(".range button").forEach((x) => x.classList.toggle("active", x === b));
    drawDetail();
  }));
  renderRecent();
  renderSummary();
  loadMarket();
}

document.addEventListener("DOMContentLoaded", init);
```

- [ ] **Step 6: 통과 확인**

Run: `.venv/Scripts/python -m pytest -v`
Expected: 모두 passed

- [ ] **Step 7: 브라우저로 직접 확인**

Run: `.venv/Scripts/python -m app` (백그라운드)
확인할 것: `http://127.0.0.1:8000`을 열면 시장 카드 3개(S&P 500 MDD에 "참고 · 점수 제외" 표시)와 "시장 n / 2"가 나온다. `AAPL`과 `005930`을 검색하면 종목 카드 3개가 추가되고 "n / 5"로 바뀐다. 카드를 클릭하면 상세 차트가 열리고 1년/5년 전환이 된다. 이동평균 상세에는 200일선·200주선이 겹쳐 그려진다. 없는 티커 `ZZZZQ`는 입력창 아래에 오류가 나온다. 폭 375px에서는 카드가 1열이 된다. 확인 후 서버를 종료한다.

- [ ] **Step 8: 커밋**

```bash
git add static tests/test_static.py
git commit -m "feat: 대시보드 화면 (카드, 종합 점수, 차트, 최근 티커)"
```

---

### Task 9: 실행 스크립트, README, 라이브 스모크 테스트

**Files:**
- Create: `run.bat`, `run.sh`, `README.md`, `tests/test_live.py`

**Interfaces:**
- Consumes: `python -m app` 진입점(Task 7), `prices.fetch_history`, `prices.resolve_symbol`, `fear_greed.fetch_fear_greed`(Task 6)

- [ ] **Step 1: 라이브 테스트 작성** — `tests/test_live.py`

```python
from __future__ import annotations

import pytest

from app.data import fear_greed, prices

pytestmark = pytest.mark.live


def test_us_history():
    s = prices.fetch_history("AAPL")
    assert len(s) > 1000
    assert s.index.tz is None


def test_korean_resolution():
    assert prices.resolve_symbol("005930", prices.fetch_history) == "005930.KS"


def test_vix_and_index():
    assert not prices.fetch_history("^VIX").empty
    assert not prices.fetch_history("^GSPC").empty


def test_fear_greed():
    data = fear_greed.fetch_fear_greed()
    assert 0 <= data["score"] <= 100
    assert len(data["history"]) > 100
```

- [ ] **Step 2: 라이브 테스트 실행**

Run: `.venv/Scripts/python -m pytest -m live -v`
Expected: 4 passed. CNN 테스트가 실패하면(차단, 형식 변경 등) 응답 내용을 확인해 `app/data/fear_greed.py`의 URL과 파싱을 고치고, `tests/test_fear_greed_data.py` 예시 payload도 실제 형식에 맞춘다. 5년치 요청이 거부되면 `HISTORY_YEARS = 1`로 줄인다.

- [ ] **Step 3: `run.bat` 작성**

```bat
@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.9+ is required. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv || (echo [ERROR] Failed to create venv & pause & exit /b 1)
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || (echo [ERROR] pip install failed & pause & exit /b 1)

echo Starting dashboard at http://127.0.0.1:8000  (Ctrl+C to stop)
".venv\Scripts\python.exe" -m app
pause
```

- [ ] **Step 4: `run.sh` 작성**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3.9+ 가 필요합니다: https://www.python.org/downloads/"; exit 1; }

[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt

echo "대시보드 실행: http://127.0.0.1:8000  (종료: Ctrl+C)"
exec .venv/bin/python -m app
```

Run: `git update-index --add --chmod=+x run.sh` (Step 7의 커밋 직전에 실행)

- [ ] **Step 5: `README.md` 작성**

````markdown
# 매수 기준 대시보드

5가지 매수 기준을 한 화면에서 확인하는 로컬 웹 대시보드입니다.

| # | 기준 | 신호 🟡 | 강한 신호 🟢 | 대상 |
|---|---|---|---|---|
| 1 | 공포·탐욕 지수 (CNN) | 25 미만 | 20 미만 | 시장 |
| 2 | VIX | 25 이상 | 30 이상 | 시장 |
| 3 | RSI(14) — 일봉 30 이하 / 주봉 35 이하 | 하나 해당 | 둘 다 해당 | 종목 |
| 4 | MDD (52주 최고 종가 대비) | −14% 이하 | −20% 이하 | 종목 |
| 5 | 200일 / 200주 이동평균 | 이평선 아래 | 이평선 아래로 5% 이상 이탈 | 종목 |

- S&P 500 MDD(사상 최고가 대비)는 참고용으로 표시하고 점수에는 넣지 않습니다.
- 페이지를 열면 시장 기준(1, 2)이 바로 계산되고, 티커를 검색하면 종목 기준(3~5)이 추가됩니다.
- 미국 티커(`AAPL`, `QQQ`)와 한국 종목코드(`005930`, 코스피 → 코스닥 순서로 자동 조회)를 지원합니다.

> 투자 판단을 돕는 참고 도구이며 투자 권유가 아닙니다. 데이터는 Yahoo Finance와 CNN의 비공식 경로를 쓰므로 지연되거나 일시적으로 조회되지 않을 수 있습니다.

## 실행

Python 3.9 이상이 필요합니다.

- **Windows**: `run.bat` 더블클릭
- **macOS / Linux**: `./run.sh`

처음 실행할 때 `.venv` 가상환경을 만들고 패키지를 설치한 뒤, 브라우저에서 `http://127.0.0.1:8000`을 엽니다.

## 기준 바꾸기

`config.yaml`의 숫자를 고치고 다시 실행하면 됩니다. 지표를 끄려면 `enabled: false`로 두세요.

## 지표 추가하기

1. `app/indicators/`에 파일을 하나 만듭니다.
2. `Indicator`를 상속하고 `@register`를 붙입니다.

```python
from app.indicators.base import NEUTRAL, SIGNAL, Indicator, register

@register
class MyIndicator(Indicator):
    id = "my_indicator"     # config.yaml의 indicators 아래 키
    name = "내 지표"
    scope = "ticker"        # "market"(실행 즉시) 또는 "ticker"(검색 시)
    scored = True           # False면 참고용 카드
    order = 70              # 화면 표시 순서

    def evaluate(self, ctx):
        s = ctx.get_daily(ctx.symbol)
        value = float(s.iloc[-1])
        status = SIGNAL if value < ctx.config["below"] else NEUTRAL
        return self.make(status=status, value=value, display=f"{value:.2f}")
```

3. `config.yaml`의 `indicators:` 아래에 `my_indicator: { enabled: true, below: 100 }`을 추가합니다.

화면은 결과를 받아 카드를 자동으로 그립니다.

## 개발

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest            # 네트워크 없는 테스트
.venv/Scripts/python -m pytest -m live    # 실제 데이터 조회 스모크 테스트
```
````

- [ ] **Step 6: `run.bat`으로 처음부터 실행해서 확인**

Run: `.venv` 폴더를 지운 뒤 `cmd /c run.bat`을 백그라운드로 실행하고, `http://127.0.0.1:8000/api/health`가 `{"status":"ok"}`를 돌려주는지 확인한다. 확인 후 종료한다.
Expected: 가상환경 생성, 설치, 서버 시작, 브라우저 열기까지 오류 없이 진행된다.

- [ ] **Step 7: 커밋**

```bash
git add run.bat run.sh README.md tests/test_live.py
git commit -m "feat: 실행 스크립트, README, 라이브 스모크 테스트"
```

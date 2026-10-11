# 매수 기준 대시보드

5가지 매수 기준을 한 화면에서 확인하는 로컬 웹 대시보드입니다.

| # | 기준 | 신호 🟡 | 강한 신호 🟢 | 대상 |
|---|---|---|---|---|
| 1 | 공포·탐욕 지수 (CNN) | 25 미만 | 20 미만 | 시장 |
| 2 | VIX | 25 이상 | 30 이상 | 시장 |
| 3 | RSI(14) — 일봉 30 이하 / 주봉 35 이하 | 하나 해당 | 둘 다 해당 | 종목 |
| 4 | MDD (52주 최고 종가 대비) | −14% 이하 | −20% 이하 | 종목 |
| 5 | 200일 / 200주 이동평균 | 둘 중 하나 아래 | 둘 다 아래 | 종목 |

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

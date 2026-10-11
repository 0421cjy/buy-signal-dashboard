# 매수 기준 대시보드 — 설계 문서

- 작성일: 2026-10-11
- 상태: 승인됨

## 1. 목적

나의 5가지 매수 기준을 한 화면에서 확인하는 **로컬 웹 대시보드**를 만든다.

- 실행 즉시 **시장 지표**(종목과 무관한 기준)를 계산해 보여준다.
- 종목(티커)을 검색하면 **종목 지표**를 추가로 계산해 보여준다.
- 다른 사람도 Python만 설치되어 있으면 자기 PC에서 쉽게 띄울 수 있어야 한다.
- 기준(지표)과 임계값을 쉽게 추가·변경할 수 있는 확장 가능한 구조여야 한다.
- 매수를 자동으로 결정하지 않는다. 기준별 충족 여부와 충족 개수만 보여준다.

### 성공 기준

1. `run.bat`(Windows) 또는 `run.sh`(macOS/Linux)를 실행하면 가상환경 생성, 의존성 설치, 서버 실행, 브라우저 열기가 자동으로 진행된다.
2. 페이지를 열면 시장 지표 2개(공포·탐욕, VIX)와 S&P 500 MDD 참고 카드가 자동으로 표시된다.
3. 미국 티커(`AAPL`)와 한국 종목코드(`005930`)를 입력하면 종목 지표 3개(RSI, 종목 MDD, 200일/200주 이평)가 추가되고, 종합 점수가 `n / 5`로 바뀐다.
4. 지표 하나의 데이터 조회가 실패해도 나머지 지표는 정상 표시된다.
5. 새 지표는 `app/indicators/`에 파일 하나를 추가하고 `config.yaml`에 임계값을 넣는 것만으로 화면에 나타난다.

### 범위 밖 (향후 확장)

- 관심종목 여러 개를 한 번에 보는 표
- 조건 충족 알림 (텔레그램, 이메일 등)
- 한글 종목명 검색
- 단일 실행 파일(.exe, PyInstaller) 및 Docker 패키징. 진입점을 분리해 두어 나중에 추가할 수 있게 한다.

## 2. 기술 스택

- **백엔드**: Python 3.9+, FastAPI, uvicorn
- **데이터**: `yfinance`(가격, VIX, S&P 500), `httpx`(CNN 공포·탐욕 지수), `pandas`
- **설정**: `config.yaml` (PyYAML)
- **프론트엔드**: 정적 HTML + Vanilla JS + CSS, Chart.js(CDN, 버전 고정). 빌드 과정이 없다.
- **테스트**: pytest, FastAPI TestClient

## 3. 디렉터리 구조

```
TradingView/
├─ run.bat / run.sh          # .venv 생성 → pip install → uvicorn 실행 → 브라우저 열기
├─ requirements.txt
├─ config.yaml               # 임계값, 캐시 시간, 서버 포트
├─ README.md                 # 실행 방법, 지표 추가 방법
├─ app/
│  ├─ main.py                # FastAPI 앱, API 라우트, static 서빙
│  ├─ config.py              # config.yaml 로드 및 기본값 병합
│  ├─ data/
│  │  ├─ prices.py           # yfinance 조회, 티커 정규화
│  │  ├─ fear_greed.py       # CNN 공포·탐욕 지수 조회
│  │  └─ cache.py            # TTL 메모리 캐시
│  └─ indicators/
│     ├─ base.py             # Indicator 기반 클래스, IndicatorResult
│     ├─ registry.py         # 지표 등록·조회
│     ├─ fear_greed.py
│     ├─ vix.py
│     ├─ rsi.py
│     ├─ mdd.py
│     └─ moving_average.py
├─ static/
│  ├─ index.html
│  ├─ app.js
│  └─ style.css
└─ tests/
```

## 4. 핵심 인터페이스

```python
class Indicator:
    id: str             # "rsi"
    name: str           # "RSI (14)"
    scope: str          # "market" | "ticker"
    scored: bool        # True면 종합 점수에 포함, False면 참고용 카드
    def evaluate(self, ctx: EvalContext) -> IndicatorResult: ...
```

`EvalContext`는 지표 설정(config 해당 섹션)과 데이터 접근 함수(가격 조회, 공포·탐욕 조회)를 담는다. 지표는 데이터 계층을 직접 import하지 않고 ctx로 주입받는다. 그래서 테스트에서 가짜 데이터로 바꿔 끼울 수 있다.

```python
IndicatorResult:
    id: str
    name: str
    scope: str
    scored: bool
    status: "strong_signal" | "signal" | "neutral" | "error" | "insufficient_data"
    value: float | None          # 대표 값
    display: str                 # 화면 표시 문자열, 예: "−16.2%"
    label: str                   # 한 줄 설명, 예: "매수 시작 구간"
    threshold: str               # 판단 기준 설명, 예: "−14% 이하 매수 시작 / −20% 이하 비중 확대"
    as_of: str | None            # 데이터 기준일 (YYYY-MM-DD)
    details: dict                # 지표별 부가 정보 (200일/200주 이격도 등)
    history: list[{date, value}] # 차트용 시계열 (최근 5년, 화면에서 1년/5년 전환)
    thresholds: list[float]      # 차트에 그릴 임계선
    error: str | None
```

새 지표는 `Indicator`를 상속하고 `registry`에 등록한다. 화면은 `IndicatorResult` 목록을 받아 카드를 자동으로 렌더링한다. `details`의 키-값은 카드 하단에 "참고" 행으로 표시한다.

## 5. 지표 계산·판정 규칙

판정 단계는 🟢 강한 신호(`strong_signal`), 🟡 신호(`signal`), ⚪ 중립(`neutral`)이다. 아래 숫자는 모두 `config.yaml` 기본값이다.

### 5.1 공포·탐욕 지수 — market
- 데이터: CNN 공포·탐욕 지수 비공식 API(`production.dataviz.cnn.io/index/fearandgreed/graphdata`). 브라우저 User-Agent 헤더가 필요하다.
- 판정: `value < 20` → strong_signal(극단적 공포) / `20 ≤ value < 25` → signal(공포) / 그 외 neutral
- 실패 시 status `error`로 처리하고 다른 지표에 영향을 주지 않는다.

### 5.2 VIX — market
- 데이터: Yahoo `^VIX` 일봉 종가
- 판정: `value ≥ 30` → strong_signal(패닉) / `25 ≤ value < 30` → signal(불안) / 그 외 neutral

### 5.3 RSI — ticker
- 계산: 일봉 종가와 주봉 종가(W-FRI 마지막 값) 각각 14기간, Wilder 평활(`alpha = 1/14` 지수평활, TradingView와 동일 방식)
- 조건: 일봉 RSI `≤ 30`, 주봉 RSI `≤ 35`
- 판정: 두 조건 모두 해당 → strong_signal / 하나만 해당 → signal / 둘 다 미해당 → neutral
- 주봉 데이터가 부족하면 주봉은 "데이터 부족"으로 표시하고 일봉 조건만으로 판정한다(최대 signal).
- details: 일봉 RSI·주봉 RSI 값과 해당 여부. 차트: 일봉 RSI, 주봉 RSI 겹쳐 그림, 임계선 30·35

### 5.4 MDD — ticker (판정) + S&P 500 (참고)
- 공통 구간과 행동: `≤ −14%` signal(헷지 자산 일부 매도 → 주식 매수 시작) / `≤ −30%` strong_signal(헷지 자산 추가 매도 → 비중 확대) / `≤ −47%` strong_signal + 경고 문구 "⚠ 극단적 하락 구간입니다"(`warning` 필드)
- **종목 MDD (`mdd`, scope ticker, scored)**
  - 현재 하락률: `현재 종가 / 올해 최고 종가 − 1`
  - 연평균 최대 하락률 A: 끝난 해별 연중 최대 하락률(그해 최고점 대비)의 평균. 거래일 200일 미만인 해와 올해는 제외
  - 구간: 매수 시작 = A, 비중 확대 = (1+A)^k₁ − 1, 극단적 하락 = (1+A)^k₂ − 1. k₁ = ln(0.70)/ln(0.86) ≈ 2.365, k₂ = ln(0.53)/ln(0.86) ≈ 4.209 (공통 구간의 남은 가격 비율 유지, −100% 미도달). 끝난 해가 3년 미만이면 공통 구간 그대로
  - 경계 비교는 소수 9자리 반올림 후 수행(부동소수점 오차 방지), 기준 문구는 소수 1자리 표시
  - details: 연평균 최대 하락률(년수), 52주 고점 대비, 사상 최고가 대비
- **S&P 500 MDD (`market_mdd`, scope market, 참고용 `scored: false`)**
  - `현재 종가 / 전체 이력 최고 종가 − 1`, 공통 구간을 그대로 적용

### 5.5 200일 / 200주 이동평균 — ticker
- 계산: 200일 SMA(일봉 종가), 200주 SMA(주봉 종가, 주 마지막 거래일 기준). 이격도 = `현재가 / SMA − 1`
- 판정: 현재가가 200일 SMA 아래, 200주 SMA 아래인지 각각 확인한다. 하나만 아래 → signal / 둘 다 아래 → strong_signal / 둘 다 위 → neutral
- details: 200일 이격도·이탈 여부, 200주 이격도·이탈 여부
- 200주 데이터가 부족하면 200주 항목을 "데이터 부족"으로 표시하고 200일만으로 판정한다(최대 signal). 200일 데이터도 부족하면 status는 `insufficient_data`다.

### 5.6 종합 점수
- 대상: `scored: true`인 지표만 (공포·탐욕, VIX, RSI, 종목 MDD, 이동평균). S&P 500 MDD는 제외한다.
- 충족 = status가 `signal` 또는 `strong_signal`
- 표시: `충족 수 / 평가된 기준 수`, 그리고 그중 강한 신호 수
- 처음 열 때: 시장 2개 기준 → "시장 n / 2"
- 종목 검색 후: 5개 기준 → "n / 5"
- `error`와 `insufficient_data`는 분모에서 빼고 "(1개 조회 실패)"처럼 별도로 표시한다.

## 6. 티커 정규화

- 공백 제거, 대문자 변환: `aapl` → `AAPL`
- 6자리 숫자: `005930.KS`로 먼저 조회하고, 데이터가 비어 있으면 `005930.KQ`로 다시 조회한다.
- 이미 접미사가 있으면(`005930.KS`, `BRK-B`) 그대로 사용한다.
- 끝까지 데이터가 없으면 `404 {"detail": "종목을 찾을 수 없습니다: XXX"}`를 반환한다.
- 응답에 정규화된 심볼과 종목명(yfinance `shortName`, 실패 시 심볼)을 포함한다.

## 7. API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | `static/index.html` |
| GET | `/api/market?refresh=0` | 시장 지표 결과 목록(공포·탐욕, VIX, S&P 500 MDD 참고) + 시장 종합 점수 |
| GET | `/api/ticker/{symbol}?refresh=0` | 종목 지표 결과 목록(RSI, 종목 MDD, 이동평균) + 종목 정보(정규화 심볼, 이름) |
| GET | `/api/health` | 상태 확인 |

5개 기준 종합 점수는 프론트엔드가 두 응답을 합쳐 계산한다. 그래야 시장 지표를 다시 조회하지 않고 종목만 추가로 조회할 수 있다.

## 8. 화면

- 상단: 제목, 티커 입력창 + 조회 버튼, 최근 조회 티커 칩(최대 5개, localStorage), 마지막 갱신 시각, 새로고침 버튼
- 종합 바: 충족 개수 점(●○), "n / m 충족 (강한 신호 k)"
- 시장 지표 섹션: 공포·탐욕, VIX 카드와 S&P 500 MDD 참고 카드("참고" 표시, 점수 제외). 페이지를 열면 바로 조회한다.
- 종목 지표 섹션: 검색 전에는 안내 문구만 보인다. 검색하면 RSI, 종목 MDD, 200일/200주 이평 카드와 참고 정보(사상 최고가 대비 하락률)를 표시한다.
- 카드 내용: 지표명, 현재 값, 상태 배지(색상 + 텍스트), 한 줄 설명, 판단 기준, 데이터 기준일, 최근 1년 미니 차트(임계선은 점선)
- 카드를 클릭하면 상세 차트 모달이 열린다(1년/5년 전환). 이동평균 카드는 가격·200일선·200주선을 함께 그린다.
- 다크/라이트 모드는 `prefers-color-scheme`을 따른다. 모바일 폭에서는 카드를 1열로 배치한다.
- 오류 표시: 카드 단위로 ⚠️ 메시지와 "다시 시도" 버튼을 보여준다. 티커 오류는 입력창 아래에 표시한다.

## 9. 캐시·에러 처리

- TTL 메모리 캐시: 키는 데이터 소스와 심볼. 기본 TTL은 600초(`config.yaml`의 `cache_ttl_seconds`).
- `refresh=1`이면 캐시를 무시하고 다시 조회한 뒤 캐시를 갱신한다.
- 외부 요청: 타임아웃 10초, 실패 시 1회 재시도
- 지표 평가는 하나씩 try/except로 감싼다. 예외가 나면 해당 결과만 `status=error`, `error=메시지`가 된다.
- 서버는 `127.0.0.1`에만 바인딩한다(기본 포트 8000, config에서 변경 가능).

## 10. config.yaml 기본값

```yaml
server:
  host: 127.0.0.1
  port: 8000
  open_browser: true
cache_ttl_seconds: 600
indicators:
  fear_greed: { enabled: true, strong_below: 20, signal_below: 25 }
  vix:        { enabled: true, strong_at_or_above: 30, signal_at_or_above: 25 }
  mdd:        { enabled: true, signal_at_or_below: -0.14, strong_at_or_below: -0.30, extreme_at_or_below: -0.47, min_years: 3, min_days_per_year: 200 }
  market_mdd: { enabled: true, index: "^GSPC", signal_at_or_below: -0.14, strong_at_or_below: -0.30, extreme_at_or_below: -0.47 }
  rsi:        { enabled: true, period: 14, daily_at_or_below: 30, weekly_at_or_below: 35 }
  moving_average: { enabled: true, daily_window: 200, weekly_window: 200 }
```

`enabled: false`로 두면 해당 지표를 계산하지도, 표시하지도 않는다.

## 11. 테스트

- **지표 단위 테스트**(네트워크 없음, 고정 시계열)
  - RSI: 알려진 입력의 Wilder RSI 값, 일봉 30·주봉 35 경계값과 조합 4가지, 주봉 데이터 부족
  - MDD: 경계값 −14%, −20%, −30%, S&P 500 MDD가 종합 점수에서 제외되는지
  - 이동평균: 이격도 경계값 0%, −4.9%, −5%, 200일·200주 조합 시 더 강한 상태 선택, 200주 데이터 부족, 200일 데이터 부족
  - 공포·탐욕: 19.9 / 20 / 24.9 / 25, VIX: 24.9 / 25 / 29.9 / 30
- **티커 정규화**: 대소문자, 6자리 숫자의 .KS → .KQ 재조회, 접미사 유지, 없는 종목
- **캐시**: TTL 만료, refresh 무시
- **API**: 가짜 데이터 계층으로 `/api/market`, `/api/ticker/{symbol}`의 응답 형태, 부분 실패, 404
- **라이브 스모크**: `pytest -m live`로 실제 네트워크 조회(기본 실행에서 제외)

## 12. 배포·실행 확장 경로

- 1차: `run.bat` / `run.sh` + `requirements.txt`
- 확장: `app/main.py`의 `run()` 함수를 진입점으로 두어 PyInstaller(.exe)나 Dockerfile에서 같은 진입점을 호출하게 한다.

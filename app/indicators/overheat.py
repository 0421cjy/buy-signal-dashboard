"""단기 과열(참고, 점수 제외): 일봉 종가로 보는 과열 조건 4가지를 몇 개 충족하는지."""
from __future__ import annotations

from app.indicators.base import EvalContext, Indicator, IndicatorResult, as_of, fmt_pct, register, to_points
from app.indicators.rsi import wilder_rsi

# 매수 신호(신호/강한 신호)와 헷갈리지 않게 이 카드만 쓰는 상태
NORMAL = "overheat_normal"
CAUTION = "overheat_caution"
OVERHEAT = "overheat"

# 단계별 행동 가이드: 라벨에 문구, 카드에 단계 막대
ACTIONS = {
    NORMAL: "보유 유지",
    CAUTION: "1차 익절 — 보유 물량 10~15% 현금화",
    OVERHEAT: "대거 익절 — 보유 물량 20~30%",
}
_STEPS = [(NORMAL, "보유", "neutral"), (CAUTION, "1차 익절", "caution"), (OVERHEAT, "대거 익절", "hot")]
WARNING = "⚠ 보유 물량 20~30% 대거 익절 — 원점 복귀 방어"


def grade(hits: int, cfg: dict) -> str:
    if hits >= cfg["overheat_at_or_above"]:
        return OVERHEAT
    if hits >= cfg["caution_at_or_above"]:
        return CAUTION
    return NORMAL


def _span(lo: int, hi: int) -> str:
    return f"{lo}개" if lo == hi else f"{lo}~{hi}개"


def stages(cfg: dict, total: int, status: str) -> list:
    """단계 막대: 단계마다 충족 개수 구간과 현재 단계 여부."""
    c, o = int(cfg["caution_at_or_above"]), int(cfg["overheat_at_or_above"])
    ranges = {NORMAL: _span(0, c - 1), CAUTION: _span(c, o - 1), OVERHEAT: _span(o, total)}
    return [{"label": label, "range": ranges[st], "tone": tone, "active": st == status} for st, label, tone in _STEPS]


def _check(hit: bool, text: str) -> str:
    return f"{'✔' if hit else '✘'} {text}"


@register
class Overheat(Indicator):
    id = "overheat"
    name = "단기 과열"
    scope = "ticker"
    scored = False
    order = 70

    def evaluate(self, ctx: EvalContext) -> IndicatorResult:
        cfg = ctx.config
        window = int(cfg["ma_window"])
        s = ctx.get_daily(ctx.symbol).dropna()
        if len(s) < window:
            return self.insufficient(f"{window}일 이동평균 계산에 데이터가 부족합니다")
        price = float(s.iloc[-1])
        sma = s.rolling(window).mean()
        gap = price / float(sma.iloc[-1]) - 1
        rsi_now = float(wilder_rsi(s, int(cfg["rsi_period"])).iloc[-1])
        days = int(cfg["surge_days"])
        surge = price / float(s.iloc[-1 - days]) - 1
        high = float(s.iloc[-252:].max())
        from_high = price / high - 1

        checks = [
            (gap >= cfg["ma_gap_at_or_above"], f"{window}일선 대비", fmt_pct(gap)),
            (rsi_now >= cfg["rsi_at_or_above"], "일봉 RSI", f"{rsi_now:.1f}"),
            (surge >= cfg["surge_at_or_above"], f"최근 {days}거래일 상승률", fmt_pct(surge)),
            (from_high >= cfg["near_high_within"], "52주 최고가 대비", fmt_pct(from_high)),
        ]
        hits = sum(hit for hit, _, _ in checks)
        status = grade(hits, cfg)
        return self.make(
            status=status,
            value=hits,
            display=f"{hits}/{len(checks)}",
            label=ACTIONS[status],
            threshold=(
                f"{window}일선 +{cfg['ma_gap_at_or_above'] * 100:.0f}% 이상 · RSI {cfg['rsi_at_or_above']:g} 이상 · "
                f"{days}거래일 +{cfg['surge_at_or_above'] * 100:.0f}% 이상 · 52주 최고가 {cfg['near_high_within'] * 100:.0f}% 이내 "
                f"— {cfg['caution_at_or_above']}개 과열 주의, {cfg['overheat_at_or_above']}개 이상 과열"
            ),
            as_of=as_of(s),
            details={name: _check(hit, text) for hit, name, text in checks},
            history=to_points(s),
            history_label="주가",
            overlays={f"{window}일선": to_points(sma)},
            warning=WARNING if status == OVERHEAT else None,
            stages=stages(cfg, len(checks), status),
        )

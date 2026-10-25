"use strict";

// 거시 지표 탭: WTI, CPI(전년 대비), 실효 기준금리, 국채 2년·10년을 한 차트(세로축 하나)에 겹쳐 그린다.
// app.js의 $, el 함수를 쓴다 (app.js 다음에 불러옴).

const TAB_KEY = "buy-signal:tab";
const MACRO_ORDER = ["DCOILWTICO", "CPIAUCSL", "DFF", "DGS2", "DGS10"];
const MACRO_COLORS = { DCOILWTICO: "#e08a1e", CPIAUCSL: "#e5484d", DFF: "#2f6fde", DGS2: "#8a4fd6", DGS10: "#12a594" };
const MACRO_YEARS = { "1y": 1, "5y": 5, "10y": 10, "20y": 20 };
// hidden: 범례로 끈 선(기간을 바꾸거나 새로고침해도 유지)
const macroState = { data: null, chart: null, range: "5y", seq: 0, tab: "signals", hidden: new Set() };

function fmtMacro(unit, value) {
  return unit === "$" ? `$${Number(value).toFixed(2)}` : `${Number(value).toFixed(2)}%`;
}

function renderMacroChips() {
  const { latest, series } = macroState.data;
  const chips = [];
  const add = (text, date) => { const c = el("span", "chip", text); if (date) c.title = `기준일 ${date}`; chips.push(c); };
  if (latest.DCOILWTICO) add(`WTI ${fmtMacro("$", latest.DCOILWTICO.value)}`, latest.DCOILWTICO.date);
  if (latest.CPIAUCSL) {
    const month = Number(latest.CPIAUCSL.date.slice(5, 7));
    add(`CPI ${latest.CPIAUCSL.value.toFixed(1)}% (${month}월, 전년 대비)`, latest.CPIAUCSL.date);
  }
  ["DFF", "DGS2", "DGS10"].forEach((sid) => {
    if (latest[sid]) add(`${series[sid].name} ${fmtMacro("%", latest[sid].value)}`, latest[sid].date);
  });
  if (latest.SPREAD_10_2) {
    const v = latest.SPREAD_10_2.value;
    add(`10년−2년 ${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)}%p`, latest.SPREAD_10_2.date);
  }
  $("macro-chips").replaceChildren(...chips);
}

function renderMacroChart() {
  const { series } = macroState.data;
  const ids = MACRO_ORDER.filter((sid) => series[sid]);
  // 가장 최근 날짜에서 선택한 기간만큼 거슬러 올라간 날짜부터
  const lastDate = ids.map((sid) => series[sid].points.at(-1)?.date || "").sort().at(-1) || "";
  const cut = new Date(lastDate);
  cut.setFullYear(cut.getFullYear() - MACRO_YEARS[macroState.range]);
  const cutoff = cut.toISOString().slice(0, 10);
  // 지표마다 날짜가 달라서(주별·월별) 날짜를 합친 가로축에 맞추고 빈 칸은 이어 그린다
  const labels = [...new Set(ids.flatMap((sid) => series[sid].points.map((p) => p.date)))]
    .filter((d) => d >= cutoff).sort();
  const datasets = ids.map((sid) => {
    const map = new Map(series[sid].points.map((p) => [p.date, p.value]));
    return {
      label: `${series[sid].name} (${series[sid].unit})`,
      unit: series[sid].unit,
      data: labels.map((d) => (map.has(d) ? map.get(d) : null)),
      borderColor: MACRO_COLORS[sid],
      backgroundColor: MACRO_COLORS[sid],
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: true,
      tension: 0,
      hidden: macroState.hidden.has(sid),
    };
  });
  if (macroState.chart) macroState.chart.destroy();
  macroState.chart = new Chart($("macro-canvas"), {
    type: "line",
    data: { labels, datasets },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: css("--muted") },
          onClick: (e, item, legend) => {
            Chart.defaults.plugins.legend.onClick.call(legend, e, item, legend);   // 기본 동작(선 켜고 끄기)
            const sid = ids[item.datasetIndex];
            if (macroState.hidden.has(sid)) macroState.hidden.delete(sid); else macroState.hidden.add(sid);
          },
        },
        tooltip: {
          callbacks: {
            label: (item) => (item.parsed.y == null ? null
              : `${item.dataset.label.replace(/ \([^)]*\)$/, "")}: ${fmtMacro(item.dataset.unit, item.parsed.y)}`),
          },
        },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 8, color: css("--muted") }, grid: { color: css("--border") } },
        y: { position: "left", ticks: { color: css("--muted") }, grid: { color: css("--border") } },
      },
    },
  });
}

async function loadMacro(refresh = false) {
  const seq = ++macroState.seq;
  const status = $("macro-status");
  status.textContent = macroState.data ? "최신 데이터 받는 중…" : "거시 지표를 불러오는 중…";
  try {
    const body = await getJSON(`/api/macro${refresh ? "?refresh=1" : ""}`);
    if (seq !== macroState.seq) return;
    macroState.data = body;
    renderMacroChips();
    if (macroState.tab === "macro") renderMacroChart();
    const t = new Date(body.fetched_at);
    status.textContent = `마지막 갱신 ${t.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}`
      + (body.failed.length ? ` · 조회 실패: ${body.failed.join(", ")}` : "");
  } catch (err) {
    if (seq !== macroState.seq) return;
    status.textContent = `거시 지표를 불러오지 못했습니다: ${err.message}`;
  }
}

function showTab(name) {
  macroState.tab = name;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $("tab-signals").hidden = name !== "signals";
  $("signals-controls").hidden = name !== "signals";
  $("tab-macro").hidden = name !== "macro";
  try { localStorage.setItem(TAB_KEY, name); } catch { /* 저장 불가 환경은 무시 */ }
  if (name === "macro") {
    if (!macroState.data) loadMacro();
    else renderMacroChart();   // 숨겨져 있던 동안 크기가 0이었으므로 보일 때 다시 그린다
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  document.querySelectorAll(".macro-range button").forEach((b) => b.addEventListener("click", () => {
    macroState.range = b.dataset.range;
    document.querySelectorAll(".macro-range button").forEach((x) => x.classList.toggle("active", x === b));
    if (macroState.data) renderMacroChart();
  }));
  $("refresh-btn").addEventListener("click", () => { if (macroState.tab === "macro") loadMacro(true); });
  let saved = "signals";
  try { saved = localStorage.getItem(TAB_KEY) || "signals"; } catch { /* 무시 */ }
  showTab(saved === "macro" ? "macro" : "signals");
});

"use strict";

// 거시 지표 카드: 시장 지표에 카드 하나(최신 값 + 1년 흐름 미니 차트), 누르면 큰 차트.
// WTI($)와 금리·CPI(%)는 단위가 달라서, 지표마다 고른 기간의 최저=0 · 최고=100으로 맞춰 흐름을 겹쳐 본다.
// app.js의 $, el, css, getJSON을 쓴다 (app.js 다음에 불러옴). app.js의 renderCards가 macroCard()를 붙인다.

const MACRO_CACHE_KEY = "buy-signal:macro";
const MACRO_ORDER = ["DCOILWTICO", "CPIAUCSL", "DFF", "DGS2", "DGS10"];
const MACRO_COLORS = { DCOILWTICO: "#e08a1e", CPIAUCSL: "#e5484d", DFF: "#2f6fde", DGS2: "#8a4fd6", DGS10: "#12a594" };
const MACRO_YEARS = { "1y": 1, "5y": 5, "10y": 10, "20y": 20 };
// hidden: 범례로 끈 선(기간을 바꿔도 유지)
const macroState = { data: null, range: "5y", seq: 0, mini: null, detail: null, hidden: new Set() };

function fmtMacro(unit, value) {
  return unit === "$" ? `$${Number(value).toFixed(2)}` : `${Number(value).toFixed(2)}%`;
}

// 고른 기간의 날짜(가로축)와, 지표별 실제 값·상대 위치(0~100)
function macroChartData(range) {
  const { series } = macroState.data;
  const ids = MACRO_ORDER.filter((sid) => series[sid]);
  const lastDate = ids.map((sid) => series[sid].points.at(-1)?.date || "").sort().at(-1) || "";
  const cut = new Date(lastDate);
  cut.setFullYear(cut.getFullYear() - MACRO_YEARS[range]);
  const cutoff = cut.toISOString().slice(0, 10);
  // 지표마다 날짜가 달라서(주별·월별) 날짜를 합친 가로축에 맞추고 빈 칸은 이어 그린다
  const labels = [...new Set(ids.flatMap((sid) => series[sid].points.map((p) => p.date)))]
    .filter((d) => d >= cutoff).sort();
  const lines = ids.map((sid) => {
    const map = new Map(series[sid].points.map((p) => [p.date, p.value]));
    const raw = labels.map((d) => (map.has(d) ? map.get(d) : null));
    const present = raw.filter((v) => v != null);
    const lo = Math.min(...present), hi = Math.max(...present);
    const scaled = raw.map((v) => (v == null ? null : hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100));
    // 툴팁용: 그 날짜에 값이 없으면(월별 CPI 등) 직전 값을 보여준다
    let carry = null;
    const asOf = raw.map((v) => (carry = v != null ? v : carry));
    return { sid, name: series[sid].name, unit: series[sid].unit, raw: asOf, scaled };
  });
  return { labels, lines };
}

function macroChartConfig(range, mini) {
  const { labels, lines } = macroChartData(range);
  const datasets = lines.map((line) => ({
    label: line.name,
    unit: line.unit,
    raw: line.raw,
    data: line.scaled,
    borderColor: MACRO_COLORS[line.sid],
    backgroundColor: MACRO_COLORS[line.sid],
    borderWidth: mini ? 1.5 : 2,
    pointRadius: 0,
    spanGaps: true,
    tension: 0,
    hidden: !mini && macroState.hidden.has(line.sid),
  }));
  return {
    type: "line",
    data: { labels, datasets },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: !mini,
          labels: { color: css("--muted") },
          onClick: (e, item, legend) => {
            Chart.defaults.plugins.legend.onClick.call(legend, e, item, legend);   // 기본 동작(선 켜고 끄기)
            const sid = lines[item.datasetIndex].sid;
            if (macroState.hidden.has(sid)) macroState.hidden.delete(sid); else macroState.hidden.add(sid);
          },
        },
        tooltip: {
          enabled: !mini,
          callbacks: {   // 차트는 0~100이지만 툴팁은 실제 값
            label: (item) => {
              const v = item.dataset.raw[item.dataIndex];
              return v == null ? null : `${item.dataset.label}: ${fmtMacro(item.dataset.unit, v)}`;
            },
          },
        },
      },
      scales: {
        x: { display: !mini, ticks: { maxTicksLimit: 8, color: css("--muted") }, grid: { color: css("--border") } },
        y: { display: !mini, min: 0, max: 100, ticks: { color: css("--muted"), stepSize: 25 }, grid: { color: css("--border") } },
      },
    },
  };
}

function macroValueRows() {
  const { latest, series } = macroState.data;
  const rows = [];
  if (latest.DCOILWTICO) rows.push(["WTI", fmtMacro("$", latest.DCOILWTICO.value)]);
  if (latest.CPIAUCSL) {
    rows.push([`CPI (${Number(latest.CPIAUCSL.date.slice(5, 7))}월)`, `${latest.CPIAUCSL.value.toFixed(1)}% 전년 대비`]);
  }
  ["DFF", "DGS2", "DGS10"].forEach((sid) => { if (latest[sid]) rows.push([series[sid].name, fmtMacro("%", latest[sid].value)]); });
  if (latest.SPREAD_10_2) {
    const v = latest.SPREAD_10_2.value;
    rows.push(["10년−2년", `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)}%p`]);
  }
  return rows;
}

// app.js renderCards("market-cards")가 시장 카드 뒤에 붙인다. 아직 데이터가 없으면 null.
function macroCard() {
  if (!macroState.data) return null;
  const card = el("article", "card neutral macro-card");
  const head = el("div", "card-head");
  const title = el("h3", null, "거시 지표");
  title.append(el("span", "tag", "참고 · 점수 제외"));
  head.append(title);
  card.append(head);
  const dl = el("dl", "details macro-values");
  macroValueRows().forEach(([k, v]) => dl.append(el("dt", null, k), el("dd", null, v)));
  card.append(dl);
  if (macroState.data.failed.length) card.append(el("div", "small", `조회 실패: ${macroState.data.failed.join(", ")}`));
  card.append(el("div", "small", "최근 1년 흐름 (지표별 최저 0 ~ 최고 100)"));
  const wrap = el("div", "mini");
  const canvas = el("canvas");
  wrap.append(canvas);
  card.append(wrap);
  requestAnimationFrame(() => {
    if (!canvas.isConnected) return;
    if (macroState.mini) macroState.mini.destroy();
    macroState.mini = new Chart(canvas, macroChartConfig("1y", true));
  });
  card.addEventListener("click", openMacroDetail);
  return card;
}

function placeMacroCard() {
  const box = $("market-cards");
  const old = box.querySelector(".macro-card");
  const card = macroCard();
  if (old && card) old.replaceWith(card);
  else if (card && box.querySelector(".card")) box.append(card);   // 시장 카드가 있을 때만 그 옆에
}

function drawMacroDetail() {
  if (macroState.detail) macroState.detail.destroy();
  macroState.detail = new Chart($("macro-canvas"), macroChartConfig(macroState.range, false));
}

function openMacroDetail() {
  $("macro-detail").showModal();
  drawMacroDetail();
}

function readMacroCache() {
  try {
    const cached = JSON.parse(localStorage.getItem(MACRO_CACHE_KEY) || "null");
    return cached && cached.series ? cached : null;
  } catch { return null; }
}

async function loadMacro(refresh = false) {
  const seq = ++macroState.seq;
  if (!macroState.data) {
    const cached = readMacroCache();   // 처음 열 때 빈 칸 대신 저장된 값을 먼저 보여준다
    if (cached) { macroState.data = cached; placeMacroCard(); }
  }
  try {
    const body = await getJSON(`/api/macro${refresh ? "?refresh=1" : ""}`);
    if (seq !== macroState.seq) return;
    macroState.data = body;
    placeMacroCard();
    if ($("macro-detail").open) drawMacroDetail();
    try { localStorage.setItem(MACRO_CACHE_KEY, JSON.stringify(body)); } catch { /* 저장 불가 환경은 무시 */ }
  } catch { /* 실패하면 저장된 값(있으면)을 그대로 둔다 */ }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".macro-range button").forEach((b) => b.addEventListener("click", () => {
    macroState.range = b.dataset.range;
    document.querySelectorAll(".macro-range button").forEach((x) => x.classList.toggle("active", x === b));
    if (macroState.data) drawMacroDetail();
  }));
  $("macro-close").addEventListener("click", () => $("macro-detail").close());
  $("macro-detail").addEventListener("click", (e) => { if (e.target === $("macro-detail")) $("macro-detail").close(); });
  $("refresh-btn").addEventListener("click", () => loadMacro(true));
  loadMacro();
});

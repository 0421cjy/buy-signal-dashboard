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

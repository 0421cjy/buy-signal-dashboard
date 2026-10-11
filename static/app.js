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
const RECENT_LIMIT = 15; // 최근 조회 티커 칩 최대 개수

// marketSeq/tickerSeq: 늦게 도착한 이전 요청의 응답이 최신 결과를 덮어쓰지 않게 하는 순번
const state = { market: [], ticker: [], tickerInfo: null, charts: {}, detail: null, detailResult: null, detailRange: "1y", marketSeq: 0, tickerSeq: 0, lastRefresh: 0 };

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

// 차트 숫자는 소수 1자리로 (예: 56.1238 → 56.1, 262000 → 262,000.0)
function fmt1(v) {
  return Number(v).toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
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
      label: `기준 ${fmt1(t)}`, isThreshold: true, data: labels.map(() => t),
      borderColor: css("--threshold"), borderDash: [4, 4], borderWidth: 1, pointRadius: 0,
    });
  });
  return {
    type: "line",
    data: { labels, datasets },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: !mini, labels: { color: css("--muted") } },
        tooltip: {
          enabled: !mini,
          // 기준선은 값이 변하지 않으므로 "기준 30: 30" 대신 "기준 30" 하나만 표시
          callbacks: { label: (item) => (item.dataset.isThreshold ? item.dataset.label : `${item.dataset.label}: ${fmt1(item.parsed.y)}`) },
        },
      },
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

function helpButton(text) {
  const wrap = el("span", "help");
  const btn = el("button", "help-btn", "?");
  btn.type = "button";
  btn.setAttribute("aria-label", `판단 기준: ${text}`);
  btn.addEventListener("click", (e) => e.stopPropagation());
  const tip = el("span", "help-tip", `기준: ${text}`);
  tip.setAttribute("role", "tooltip");
  wrap.append(btn, tip);
  return wrap;
}

function buildCard(r, containerId, onRetry) {
  const st = STATUS[r.status] || STATUS.neutral;
  const card = el("article", `card ${st.cls}${r.warning ? " extreme" : ""}`);

  const head = el("div", "card-head");
  const title = el("h3", null, r.name);
  if (!r.scored) title.append(el("span", "tag", "참고 · 점수 제외"));
  const side = el("div", "card-side");
  if (r.threshold) side.append(helpButton(r.threshold));
  side.append(el("span", `badge ${st.cls}`, st.text));
  head.append(title, side);
  card.append(head);

  card.append(el("div", "value", r.display || "—"));
  if (r.label) card.append(el("div", "label", r.label));
  if (r.warning) card.append(el("div", "warning", r.warning));

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

// 새로고침이면 기존 카드를 그대로 둔 채(흐리게) 응답을 기다렸다가 한 번에 교체한다
function setRefreshing(containerId, on) {
  $(containerId).classList.toggle("refreshing", on);
}

async function loadMarket(refresh = false) {
  const seq = ++state.marketSeq;
  const keep = refresh && state.market.length > 0;
  if (keep) setRefreshing("market-cards", true);
  else renderMessage("market-cards", "시장 지표를 불러오는 중…");
  try {
    const body = await getJSON(`/api/market${refresh ? "?refresh=1" : ""}`);
    if (seq !== state.marketSeq) return;
    state.market = body.results;
    renderCards("market-cards", state.market, () => loadMarket(true));
    setUpdated(body.fetched_at);
  } catch (err) {
    if (seq !== state.marketSeq) return;
    if (keep) {
      $("updated").textContent = `갱신 실패: ${err.message}`;
    } else {
      state.market = [];
      renderMessage("market-cards", `시장 지표를 불러오지 못했습니다: ${err.message}`);
    }
  } finally {
    if (seq === state.marketSeq) setRefreshing("market-cards", false);
  }
  renderSummary();
}

async function loadTicker(raw, refresh = false) {
  const symbol = raw.trim();
  if (!symbol) return;
  const seq = ++state.tickerSeq;
  const keep = refresh && state.tickerInfo !== null;
  $("ticker-error").hidden = true;
  if (keep) setRefreshing("ticker-cards", true);
  else renderMessage("ticker-cards", `${symbol} 조회 중…`);
  try {
    const body = await getJSON(`/api/ticker/${encodeURIComponent(symbol)}${refresh ? "?refresh=1" : ""}`);
    if (seq !== state.tickerSeq) return;
    state.ticker = body.results;
    state.tickerInfo = { symbol: body.symbol, name: body.name };
    $("ticker-title").textContent = `종목 지표 · ${body.name} (${body.symbol})`;
    renderCards("ticker-cards", state.ticker, () => loadTicker(body.symbol, true));
    rememberTicker(body.symbol);
    setUpdated(body.fetched_at);
  } catch (err) {
    if (seq !== state.tickerSeq) return;
    $("ticker-error").textContent = keep ? `갱신 실패: ${err.message}` : err.message;
    $("ticker-error").hidden = false;
    if (keep) {
      // 기존 카드 유지
    } else if (!state.tickerInfo) {
      renderMessage("ticker-cards", "티커를 검색하면 RSI, MDD(52주 고점 대비), 200일/200주 이동평균을 확인할 수 있습니다.");
    } else {
      renderCards("ticker-cards", state.ticker, () => loadTicker(state.tickerInfo.symbol, true));
    }
  } finally {
    if (seq === state.tickerSeq) setRefreshing("ticker-cards", false);
  }
  renderSummary();
}

function readRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch { return []; }
}

function rememberTicker(symbol) {
  const list = [symbol, ...readRecent().filter((s) => s !== symbol)].slice(0, RECENT_LIMIT);
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

async function refreshAll() {
  const btn = $("refresh-btn");
  if (btn.disabled) return; // 이미 갱신 중
  btn.disabled = true;
  btn.textContent = "갱신 중…";
  state.lastRefresh = Date.now();
  const jobs = [loadMarket(true)];
  if (state.tickerInfo) jobs.push(loadTicker(state.tickerInfo.symbol, true));
  await Promise.allSettled(jobs);
  btn.disabled = false;
  btn.textContent = "새로고침";
}

// 탭이 보이는 동안에만 일정 간격으로 refreshAll. 숨겨져 있던 탭은 다시 보일 때 간격이 지났으면 바로 갱신한다.
function startAutoRefresh(minutes) {
  if (!(minutes > 0)) return;
  const intervalMs = minutes * 60 * 1000;
  $("auto-refresh").textContent = `· ${minutes}분마다 자동 갱신`;
  const due = () => !document.hidden && Date.now() - state.lastRefresh >= intervalMs;
  setInterval(() => { if (due()) refreshAll(); }, Math.min(30000, intervalMs / 2));
  document.addEventListener("visibilitychange", () => { if (due()) refreshAll(); });
}

function init() {
  $("search-form").addEventListener("submit", (e) => { e.preventDefault(); loadTicker($("ticker-input").value); });
  fetch("/static/tickers.json")
    .then((res) => res.json())
    .then((items) => attachSuggest($("ticker-input"), $("suggest-list"), items, (symbol) => loadTicker(symbol)))
    .catch(() => {}); // 목록을 못 불러와도 직접 입력 조회는 그대로 동작
  $("refresh-btn").addEventListener("click", refreshAll);
  $("detail-close").addEventListener("click", () => $("detail").close());
  $("detail").addEventListener("click", (e) => { if (e.target === $("detail")) $("detail").close(); });
  document.querySelectorAll(".range button").forEach((b) => b.addEventListener("click", () => {
    state.detailRange = b.dataset.range;
    document.querySelectorAll(".range button").forEach((x) => x.classList.toggle("active", x === b));
    drawDetail();
  }));
  renderRecent();
  renderSummary();
  state.lastRefresh = Date.now();
  loadMarket();
  getJSON("/api/settings").then((s) => startAutoRefresh(s.auto_refresh_minutes)).catch(() => {});
}

document.addEventListener("DOMContentLoaded", init);

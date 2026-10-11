"use strict";

// 주요 종목 미리보기(자동완성). static/tickers.json 목록에서 티커·종목코드·영문/한글 이름·별칭으로 찾는다.

const MARKET_TEXT = { US: "미국", ETF: "ETF", INDEX: "지수", KOSPI: "코스피", KOSDAQ: "코스닥" };

function normalizeQuery(text) {
  return text.trim().toLowerCase().replace(/\s+/g, "");
}

// 점수가 낮을수록 위에 표시: 티커 일치 > 티커 앞부분 > 이름 앞부분 > 이름 포함
function matchScore(item, q) {
  const symbol = item.symbol.toLowerCase();
  const code = symbol.replace(/^\^/, "").replace(/\.(ks|kq)$/, "");
  if (symbol === q || code === q) return 0;
  if (symbol.startsWith(q) || code.startsWith(q)) return 1;
  const names = [item.name, item.ko || "", ...(item.aliases || [])].map((n) => n.toLowerCase());
  // 앞부분은 띄어쓰기를 무시하고("삼성 전자" → 삼성전자), 중간 포함은 띄어쓰기를 살려 비교한다
  // ("aa"가 "hanwha aerospace"의 단어 경계를 넘어 걸리지 않게)
  if (names.some((n) => normalizeQuery(n).startsWith(q))) return 2;
  if (names.some((n) => n.includes(q))) return 3;
  return null;
}

function matchTickers(items, text, limit = 8) {
  const q = normalizeQuery(text);
  if (!q) return [];
  return items
    .map((item, index) => ({ item, index, score: matchScore(item, q) }))
    .filter((m) => m.score !== null)
    .sort((a, b) => a.score - b.score || a.index - b.index)
    .slice(0, limit)
    .map((m) => m.item);
}

// input 아래에 후보 목록을 붙인다. 후보를 고르면 onPick(symbol)을 부른다.
function attachSuggest(input, list, items, onPick) {
  let matches = [];
  let active = -1;

  function close() {
    matches = [];
    active = -1;
    list.hidden = true;
    list.replaceChildren();
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function highlight(index) {
    active = index;
    [...list.children].forEach((li, i) => li.classList.toggle("active", i === active));
    if (active >= 0) input.setAttribute("aria-activedescendant", list.children[active].id);
    else input.removeAttribute("aria-activedescendant");
  }

  function pick(item) {
    close();
    input.value = item.symbol;
    onPick(item.symbol);
  }

  function render() {
    matches = matchTickers(items, input.value);
    if (matches.length === 0) return close();
    list.replaceChildren(...matches.map((item, i) => {
      const li = document.createElement("li");
      li.id = `suggest-${i}`;
      li.setAttribute("role", "option");
      const title = document.createElement("span");
      title.className = "suggest-name";
      title.textContent = item.ko && item.ko !== item.name ? `${item.ko} · ${item.name}` : item.name;
      const meta = document.createElement("span");
      meta.className = "suggest-meta";
      meta.textContent = `${item.symbol} · ${MARKET_TEXT[item.market] || item.market}`;
      li.append(title, meta);
      // mousedown에서 막아야 input blur로 목록이 먼저 닫히지 않는다
      li.addEventListener("mousedown", (e) => { e.preventDefault(); pick(item); });
      li.addEventListener("mousemove", () => highlight(i));
      return li;
    }));
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    highlight(-1);
  }

  input.addEventListener("input", render);
  input.addEventListener("focus", () => { if (input.value.trim()) render(); });
  input.addEventListener("blur", close);
  input.addEventListener("keydown", (e) => {
    if (list.hidden) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlight((active + 1) % matches.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlight(active <= 0 ? matches.length - 1 : active - 1);
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault(); // 고른 후보로 조회 (폼 제출 대신)
      pick(matches[active]);
    } else if (e.key === "Escape") {
      close();
    }
  });

  return { close };
}

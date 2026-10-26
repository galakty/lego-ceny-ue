"use strict";

const PAGE = 60;
const AGE_SPAN = 3; // keep in sync with pages.AGE_SPAN
const $ = (id) => document.getElementById(id);
const pln = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });
const eur = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "EUR" });
const int = new Intl.NumberFormat("pl-PL");
const els = {
  q: $("q"), age: $("age"), pmin: $("pmin"), pmax: $("pmax"), theme: $("theme"),
  offers: $("offers"), sort: $("sort"), list: $("list"), count: $("count"), more: $("more"),
  chips: $("piece-chips"), reset: $("reset"), detail: $("detail"), ageHint: $("age-hint"),
};
// URL parameter names, so filtered views can be shared, e.g. ?wiek=6&od=500
const PARAMS = { q: "q", age: "wiek", pmin: "od", pmax: "do", theme: "seria", offers: "ceny", sort: "sort" };

let sets = [];
let filtered = [];
let shown = 0;

const best = (s) => s.offers[0] || null;
const bestCost = (s) => { const o = best(s); return o ? (o.total ?? o.pln) : null; };

function ageLabel(s) {
  if (s.age_min == null) return "";
  return s.age_max ? `${s.age_min}–${s.age_max} lat` : `${s.age_min}+`;
}

// Polish plural forms: 1 klocek, 2-4 klocki, 5+ klocków (but 12-14 klocków, 22 klocki)
function plural(n, one, few, many) {
  const last = n % 10, lastTwo = n % 100;
  if (n === 1) return one;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return few;
  return many;
}
const piecesWord = (n) => plural(n, "klocek", "klocki", "klocków");

function readFilters() {
  return {
    q: els.q.value.trim().toLowerCase(),
    age: els.age.value === "" ? null : Number(els.age.value),
    pmin: els.pmin.value === "" ? null : Number(els.pmin.value),
    pmax: els.pmax.value === "" ? null : Number(els.pmax.value),
    theme: els.theme.value,
    offers: els.offers.checked,
    sort: els.sort.value,
  };
}

function matches(s, f) {
  if (f.q && !s.name.toLowerCase().includes(f.q) && !s.num.startsWith(f.q)) return false;
  if (f.pmin != null && s.pieces < f.pmin) return false;
  if (f.pmax != null && s.pieces > f.pmax) return false;
  if (f.theme && s.theme !== f.theme) return false;
  if (f.offers && !s.offers.length) return false;
  if (f.age != null) {
    // only sets aimed at this age: a "2+" Duplo set is technically fine for a 6-year-old, but not what a parent wants
    if (s.age_min == null || s.age_min > f.age || s.age_min < f.age - AGE_SPAN) return false;
    if (s.age_max != null && s.age_max < f.age) return false;
  }
  return true;
}

const SORTS = {
  "new": (a, b) => b.year - a.year || b.num.localeCompare(a.num),
  "pieces-desc": (a, b) => b.pieces - a.pieces,
  "pieces-asc": (a, b) => a.pieces - b.pieces,
  // sets without a price go last
  "price-asc": (a, b) => (bestCost(a) ?? Infinity) - (bestCost(b) ?? Infinity),
  "ppp-asc": (a, b) => ((bestCost(a) ?? Infinity) / a.pieces) - ((bestCost(b) ?? Infinity) / b.pieces),
};

function apply() {
  const f = readFilters();
  filtered = sets.filter((s) => matches(s, f)).sort(SORTS[f.sort] || SORTS.new);
  shown = 0;
  els.list.replaceChildren();
  els.count.textContent = `${int.format(filtered.length)} ${plural(filtered.length, "zestaw", "zestawy", "zestawów")}`;
  syncChips(f);
  syncUrl(f);
  showMore();
}

function showMore() {
  const frag = document.createDocumentFragment();
  for (const s of filtered.slice(shown, shown + PAGE)) frag.append(card(s));
  els.list.append(frag);
  shown = Math.min(shown + PAGE, filtered.length);
  els.more.hidden = shown >= filtered.length;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v; else node.setAttribute(k, v);
  }
  node.append(...children.filter((c) => c != null && c !== ""));
  return node;
}

function card(s) {
  const cost = bestCost(s);
  const meta = [s.num, `${int.format(s.pieces)} ${piecesWord(s.pieces)}`, ageLabel(s)].filter(Boolean).join(" · ");
  const li = el("li", {},
    el("article", { class: "card", tabindex: "0", role: "button", "aria-label": `${s.name}, szczegóły` },
      el("div", { class: "img" }, s.img ? el("img", { src: s.img, alt: "", loading: "lazy" }) : null),
      el("div", { class: "body" },
        el("h2", {}, s.name),
        el("div", { class: "meta" }, meta),
        el("div", { class: "meta" }, [s.theme, s.year].filter(Boolean).join(" · ")),
        cost != null
          ? el("div", { class: "price" }, `od ${pln.format(cost)}`)
          : el("div", { class: "price none" }, "Brak cen"))));
  const article = li.firstChild;
  article.addEventListener("click", () => openDetail(s));
  article.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDetail(s); } });
  return li;
}

function historyChart(history) {
  if (history.length < 2) return null;
  const w = 600, h = 120, pad = 8;
  const values = history.map(([, p]) => p);
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const x = (i) => pad + (i * (w - 2 * pad)) / (history.length - 1);
  const y = (p) => h - pad - ((p - min) * (h - 2 * pad)) / span;
  const points = history.map(([, p], i) => `${x(i).toFixed(1)},${y(p).toFixed(1)}`).join(" ");
  const wrap = el("div", { class: "chart" }, el("strong", {}, "Najniższa cena w czasie"));
  wrap.insertAdjacentHTML("beforeend",
    `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Wykres ceny od ${pln.format(min)} do ${pln.format(max)}">` +
    `<polyline points="${points}" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`);
  wrap.append(el("div", { class: "meta" },
    `${history[0][0]} – ${history[history.length - 1][0]}: od ${pln.format(min)} do ${pln.format(max)}`));
  return wrap;
}

function offersTable(s) {
  if (!s.offers.length) return el("p", { class: "meta" }, "Nie mamy jeszcze cen dla tego zestawu.");
  const rows = s.offers.map((o, i) => el("tr", { class: i === 0 ? "best" : null },
    el("td", {}, el("a", { href: o.url, target: "_blank", rel: "noopener nofollow" }, o.shop)),
    el("td", {}, o.country),
    el("td", { class: "num" }, o.currency === "PLN" ? pln.format(o.pln) : `${new Intl.NumberFormat("pl-PL", { style: "currency", currency: o.currency }).format(o.price)} (${pln.format(o.pln)})`),
    el("td", { class: "num" }, o.shipping != null ? pln.format(o.shipping) : (o.ships_to_pl === false ? "nie wysyła do PL" : "?")),
    el("td", { class: "num" }, o.total != null ? pln.format(o.total) : "–")));
  return el("table", {},
    el("thead", {}, el("tr", {},
      el("th", {}, "Sklep"), el("th", {}, "Kraj"), el("th", { class: "num" }, "Cena"),
      el("th", { class: "num" }, "Dostawa do PL"), el("th", { class: "num" }, "Razem"))),
    el("tbody", {}, ...rows));
}

function affiliateLinks(s) {
  const programs = window.AFFILIATES || [];
  if (!programs.length) return null;
  return el("p", { class: "shop-links" }, ...programs.map((a) => {
    const url = `${a.search_url}?${new URLSearchParams({ k: `LEGO ${s.num}`, tag: a.tag })}`;
    return el("a", { class: "shop-btn", href: url, rel: "sponsored nofollow noopener", target: "_blank" }, `Sprawdź na ${a.name}`);
  }));
}

function openDetail(s) {
  const close = el("button", { class: "close", type: "button", "aria-label": "Zamknij" }, "×");
  close.addEventListener("click", () => els.detail.close());
  const facts = [
    `Numer ${s.num}`, `${int.format(s.pieces)} ${piecesWord(s.pieces)}`,
    ageLabel(s) && `wiek ${ageLabel(s)}`, s.theme, s.year,
  ].filter(Boolean).join(" · ");
  const refPrice = s.lego_de_eur ? el("p", { class: "meta" }, `Cena katalogowa LEGO w Niemczech: ${eur.format(s.lego_de_eur)}`) : null;
  els.detail.replaceChildren(el("div", { class: "detail" },
    el("header", {},
      s.img ? el("img", { src: s.img, alt: s.name }) : null,
      el("div", {}, el("h2", {}, s.name), el("div", { class: "meta" }, facts), refPrice,
        el("p", {}, el("a", { href: `zestaw/${s.num}/` }, "Strona zestawu →"))),
      close),
    offersTable(s),
    affiliateLinks(s),
    historyChart(s.history)));
  els.detail.showModal();
}

function syncChips(f) {
  for (const b of els.chips.querySelectorAll("button")) {
    const min = b.dataset.min === "" ? null : Number(b.dataset.min);
    const max = b.dataset.max === "" ? null : Number(b.dataset.max);
    b.setAttribute("aria-pressed", String(min === f.pmin && max === f.pmax));
  }
}

function syncUrl(f) {
  const p = new URLSearchParams();
  if (f.q) p.set(PARAMS.q, els.q.value.trim());
  if (f.age != null) p.set(PARAMS.age, f.age);
  if (f.pmin != null) p.set(PARAMS.pmin, f.pmin);
  if (f.pmax != null) p.set(PARAMS.pmax, f.pmax);
  if (f.theme) p.set(PARAMS.theme, f.theme);
  if (f.offers) p.set(PARAMS.offers, "1");
  if (f.sort !== "new") p.set(PARAMS.sort, f.sort);
  const qs = p.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function readUrl() {
  const p = new URLSearchParams(location.search);
  els.q.value = p.get(PARAMS.q) || "";
  els.age.value = p.get(PARAMS.age) || "";
  els.pmin.value = p.get(PARAMS.pmin) || "";
  els.pmax.value = p.get(PARAMS.pmax) || "";
  els.theme.value = p.get(PARAMS.theme) || "";
  els.offers.checked = p.get(PARAMS.offers) === "1";
  els.sort.value = p.get(PARAMS.sort) || "new";
}

function fillSelects() {
  for (let a = 1; a <= 18; a++) els.age.append(el("option", { value: a }, a === 18 ? "18 lat i więcej" : `${a} ${a === 1 ? "rok" : a < 5 ? "lata" : "lat"}`));
  const themes = [...new Set(sets.map((s) => s.theme).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pl"));
  for (const t of themes) els.theme.append(el("option", { value: t }, t));
  const withAge = sets.filter((s) => s.age_min != null).length;
  els.ageHint.textContent = withAge < sets.length ? `Wiek znamy dla ${int.format(withAge)} z ${int.format(sets.length)} zestawów.` : "";
}

let timer;
const debounced = () => { clearTimeout(timer); timer = setTimeout(apply, 150); };

els.chips.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  const pressed = b.getAttribute("aria-pressed") === "true";
  els.pmin.value = pressed ? "" : b.dataset.min;
  els.pmax.value = pressed ? "" : b.dataset.max;
  apply();
});
for (const input of [els.q, els.pmin, els.pmax]) input.addEventListener("input", debounced);
for (const input of [els.age, els.theme, els.offers, els.sort]) input.addEventListener("change", apply);
els.more.addEventListener("click", showMore);
els.reset.addEventListener("click", () => {
  els.q.value = els.age.value = els.pmin.value = els.pmax.value = els.theme.value = "";
  els.offers.checked = false;
  els.sort.value = "new";
  apply();
});
els.detail.addEventListener("click", (e) => { if (e.target === els.detail) els.detail.close(); });

if (matchMedia("(max-width: 760px)").matches) $("filters-box").open = false;

fetch("data/sets.json")
  .then((r) => r.json())
  .then((data) => { sets = data; fillSelects(); readUrl(); apply(); })
  .catch(() => { els.count.textContent = "Nie udało się wczytać danych."; });

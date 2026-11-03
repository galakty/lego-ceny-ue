"use strict";
// Gift finder: child's age + budget + interests -> the five sets with the most pieces for the money.
// Runs in the browser on the same data/sets.json as the search on the home page.

const ROOT = "../../";
const SHOWN = 5;
const AGE_SPAN = 3; // keep in sync with pages.AGE_SPAN
const $ = (id) => document.getElementById(id);
const pln = new Intl.NumberFormat("pl-PL", { style: "currency", currency: "PLN" });
const int = new Intl.NumberFormat("pl-PL");

// Polish plural forms: 1 klocek, 2-4 klocki, 5+ klocków (but 12-14 klocków, 22 klocki)
function plural(n, one, few, many) {
  const last = n % 10, lastTwo = n % 100;
  if (n === 1) return one;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return few;
  return many;
}

// interest -> theme name fragments and name words (set names come from Rebrickable, so they are English)
const INTERESTS = {
  auta: { themes: ["speed champions"], words: /\b(cars?|trucks?|race|racing|racers?|bus|tractors?|motorcycles?|motorbikes?|jeep|van|vehicles?|lamborghini|ferrari|porsche|mclaren|bmw|mercedes|bugatti|aston martin|formula|f1|kart|ambulance|fire engine)\b/i, not: ["super mario"] },
  zwierzeta: { themes: ["animal crossing"], words: /\b(animals?|dogs?|puppy|puppies|cats?|kittens?|horses?|pony|ponies|bunny|bunnies|rabbits?|panda|unicorns?|farm|zoo|vet|pets?|birds?|owls?|fox|bears?|dolphins?|sharks?|tigers?|lions?|elephants?|koalas?|hedgehogs?|penguins?|turtles?|whales?)\b/i },
  minecraft: { themes: ["minecraft"] },
  kosmos: { themes: ["star wars"], words: /\b(space|rocket|astronauts?|shuttle|mars|moon|lunar|planets?|galaxy|spaceship)\b/i },
  superbohaterowie: { themes: ["super heroes", "marvel", "batman", "spider-man", "dc "] },
  disney: { themes: ["disney", "princess", "frozen", "wish"], words: /\b(princess|frozen|elsa|ariel|moana|stitch)\b/i },
  dinozaury: { themes: ["jurassic"], words: /\b(dinosaurs?|dino|t\. ?rex|raptors?|triceratops)\b/i },
  miasto: { themes: ["city", "architecture"] },
  harrypotter: { themes: ["harry potter", "wizarding"] },
  ninjago: { themes: ["ninjago"] },
  gry: { themes: ["super mario", "sonic", "animal crossing", "fortnite"] },
  technika: { themes: ["technic", "mindstorms", "spike"], words: /\b(robots?|mechs?)\b/i },
  kwiaty: { themes: ["botanical"], words: /\b(flowers?|bouquets?|orchids?|roses?|tulips?|bonsai|succulents?|blossoms?|sunflowers?|wildflowers?|poinsettias?|lil(y|ies)|dais(y|ies)|peon(y|ies))\b/i, not: ["super mario", "speed champions"] },
};

function interestMatch(s, key) {
  const it = INTERESTS[key];
  const theme = (s.theme || "").toLowerCase();
  if ((it.not || []).some((t) => theme.includes(t))) return false;
  return it.themes.some((t) => theme.includes(t)) || (it.words ? it.words.test(s.name) : false);
}

// cheapest offer not marked as sold out (sold-out shops are already left out of the data)
const bestOffer = (s) => s.offers.find((o) => o.in_stock !== false) || null;
const cost = (o) => o.total ?? o.pln;

function fitsAge(s, age) {
  if (age == null) return true;
  if (age >= 16) return s.age_min != null && s.age_min >= 14; // "dorosły": sets for teens and adults
  return s.age_min != null && s.age_min <= age && s.age_min >= age - AGE_SPAN && (s.age_max == null || s.age_max >= age);
}

function pick(sets, f) {
  return sets
    .map((s) => ({ s, o: bestOffer(s) }))
    .filter(({ s, o }) => o && cost(o) <= f.budget && fitsAge(s, f.age)
      && (!f.interests.length || f.interests.some((k) => interestMatch(s, k))))
    // most pieces for the money first: a bigger set within the same budget is the better gift
    .sort((a, b) => b.s.pieces - a.s.pieces || cost(a.o) - cost(b.o));
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) node.setAttribute(k === "class" ? "class" : k, v);
  node.append(...children.filter((c) => c != null && c !== ""));
  return node;
}

function ageText(s) {
  if (s.age_min == null) return "";
  return s.age_max ? `${s.age_min}–${s.age_max} lat` : `${s.age_min}+`;
}

function card({ s, o }) {
  const price = cost(o);
  const low = s.low_30d != null && price <= s.low_30d + 0.005
    ? el("div", { class: "low30 best" }, "Najtaniej od 30 dni")
    : (s.low_30d != null ? el("div", { class: "low30" }, `Najniżej w 30 dni: ${pln.format(s.low_30d)}`) : null);
  return el("li", { class: "gift" },
    el("a", { class: "img", href: `${ROOT}zestaw/${s.num}/` }, s.img ? el("img", { src: s.img, alt: "", loading: "lazy" }) : null),
    el("div", { class: "body" },
      el("h2", {}, el("a", { href: `${ROOT}zestaw/${s.num}/` }, s.name)),
      el("div", { class: "meta" }, [s.num, `${int.format(s.pieces)} ${plural(s.pieces, "klocek", "klocki", "klocków")}`, ageText(s), s.theme].filter(Boolean).join(" · ")),
      el("div", { class: "price" }, pln.format(price)),
      s.pieces ? el("div", { class: "meta" }, `${pln.format(price / s.pieces)} za klocek`) : null,
      low,
      el("a", { class: "shop-btn", href: o.url, target: "_blank", rel: `${o.sponsored ? "sponsored " : ""}nofollow noopener` },
        `Kup w ${o.shop} →`)));
}

const els = { age: $("g-age"), budget: $("g-budget"), interests: $("g-interests"), list: $("g-list"), count: $("g-count"), more: $("g-more") };
let sets = [];
let found = [];
let shown = 0;

function read() {
  const pressed = (box) => [...box.querySelectorAll("button[aria-pressed=true]")].map((b) => b.dataset.value);
  const budget = pressed(els.budget)[0];
  return {
    age: els.age.value === "" ? null : Number(els.age.value),
    budget: budget === "" || budget == null ? Infinity : Number(budget),
    interests: pressed(els.interests),
  };
}

function render() {
  const f = read();
  found = pick(sets, f);
  shown = 0;
  els.list.replaceChildren();
  els.count.textContent = found.length
    ? `${plural(found.length, "Pasuje", "Pasują", "Pasuje")} ${int.format(found.length)} ${plural(found.length, "zestaw", "zestawy", "zestawów")}. Najpierw te z największą liczbą klocków w Twoim budżecie.`
    : "Nic nie pasuje. Zwiększ budżet albo odznacz część zainteresowań.";
  showMore();
  syncUrl(f);
}

function showMore() {
  els.list.append(...found.slice(shown, shown + SHOWN).map(card));
  shown = Math.min(shown + SHOWN, found.length);
  els.more.hidden = shown >= found.length;
}

function syncUrl(f) {
  const p = new URLSearchParams();
  if (f.age != null) p.set("wiek", f.age);
  if (f.budget !== Infinity) p.set("budzet", f.budget);
  if (f.interests.length) p.set("tematy", f.interests.join(","));
  history.replaceState(null, "", p.toString() ? `?${p}` : location.pathname);
}

function readUrl() {
  const p = new URLSearchParams(location.search);
  if (p.has("wiek")) els.age.value = p.get("wiek");
  if (p.has("budzet")) for (const b of els.budget.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.value === p.get("budzet")));
  const topics = (p.get("tematy") || "").split(",");
  for (const b of els.interests.querySelectorAll("button")) b.setAttribute("aria-pressed", String(topics.includes(b.dataset.value)));
}

els.budget.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  for (const x of els.budget.querySelectorAll("button")) x.setAttribute("aria-pressed", String(x === b));
  render();
});
els.interests.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true"));
  render();
});
els.age.addEventListener("change", render);
els.more.addEventListener("click", showMore);

fetch(`${ROOT}data/sets.json`)
  .then((r) => r.json())
  .then((data) => { sets = data; readUrl(); render(); })
  .catch(() => { els.count.textContent = "Nie udało się wczytać danych. Odśwież stronę."; });

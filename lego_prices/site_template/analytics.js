// Counts clicks to shops as GoatCounter events, so we can see which shops and buttons people use.
document.addEventListener("click", (e) => {
  const a = e.target.closest("a[href^='http']");
  if (!a || new URL(a.href).hostname === location.hostname || !window.goatcounter || !window.goatcounter.count) return;
  window.goatcounter.count({ path: `klik: ${a.textContent.trim().slice(0, 60)}`, title: location.pathname, event: true });
});

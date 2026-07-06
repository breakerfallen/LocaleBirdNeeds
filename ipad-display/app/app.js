// Shared client helpers. All data comes from the local server (same origin),
// which is the only thing that talks to eBird. No external calls from here.

// The household ("people") comes from /api/config — ids, display names, and
// per-bird `needs` flags all key off it, so nothing person-specific is
// hardcoded in these pages.
const PERSON_COLORS = [
  "var(--you, #3f6f52)", "var(--mel, #6a4a7a)",
  "var(--p2, #8a6d3b)", "var(--p3, #3b6e8a)",
];
const personColor = (i) => PERSON_COLORS[i % PERSON_COLORS.length];
const peopleOf = (cfg) => (cfg && cfg.people) || [];
const needsFor = (obj, pid) => !!(obj && obj.needs && obj.needs[pid]);
const needsAny = (obj) => !!(obj && obj.needs && Object.values(obj.needs).some(Boolean));

// Theme: applied instantly from localStorage by an inline <head> script on each
// page (no flash); server settings.json is the source of truth and reconciles
// here once /api/config loads.
function applyTheme(theme) {
  try {
    if (!theme) return;
    localStorage.setItem("nn-theme", theme);
    document.documentElement.classList.toggle("dark", theme === "dark");
  } catch (e) {}
}

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    let msg = `${url} failed: ${r.status}`;
    try {
      const j = await r.json();
      if (j && j.error) msg = j.error;
    } catch {}
    throw new Error(msg);
  }
  return r.json();
}

const fetchConfig = () => getJSON("/api/config");
const fetchNearby = () => getJSON("/api/nearby");
const fetchSpecies = (code) => getJSON(`/api/species?code=${encodeURIComponent(code)}`);

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.replace(" ", "T"));
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function speciesLinkParams(obs) {
  const p = new URLSearchParams({
    code: obs.speciesCode || "",
    common: obs.comName || "",
    sci: obs.sciName || "",
  });
  return `species.html?${p.toString()}`;
}

function escapeHTML(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

/*
 * Kenteken check — haalt basisgegevens van een voertuig op via de open data
 * van de RDW (Socrata / SODA API). Er is geen API-sleutel of backend nodig;
 * de aanvraag gaat rechtstreeks vanuit de browser van de bezoeker.
 */

// Gekentekende voertuigen (algemene gegevens)
const VEHICLE_URL = "https://opendata.rdw.nl/resource/m9d7-ebf2.json";
// Gekentekende voertuigen — brandstof
const FUEL_URL = "https://opendata.rdw.nl/resource/8ys7-d773.json";

const form = document.getElementById("lookup-form");
const input = document.getElementById("plate");
const submitBtn = document.getElementById("submit-btn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const titleEl = document.getElementById("result-title");
const plateEl = document.getElementById("result-plate");
const gridEl = document.getElementById("result-grid");
const sourceLink = document.getElementById("source-link");

/** Normaliseer een kenteken: hoofdletters, alleen letters/cijfers. */
function normalizePlate(value) {
  return (value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

/** Zet YYYYMMDD (RDW-formaat) om naar DD-MM-JJJJ. */
function formatDate(raw) {
  if (!raw) return null;
  const s = String(raw).slice(0, 8);
  if (!/^\d{8}$/.test(s)) return raw;
  return `${s.slice(6, 8)}-${s.slice(4, 6)}-${s.slice(0, 4)}`;
}

/** Getal met duizendtal-scheiding (NL). */
function formatNumber(raw, suffix = "") {
  if (raw === undefined || raw === null || raw === "") return null;
  const n = Number(raw);
  if (Number.isNaN(n)) return raw;
  return n.toLocaleString("nl-NL") + suffix;
}

/** Bedrag in euro's. */
function formatEuro(raw) {
  if (raw === undefined || raw === null || raw === "") return null;
  const n = Number(raw);
  if (Number.isNaN(n)) return raw;
  return n.toLocaleString("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

/** Nette weergave van het kenteken met streepjes waar mogelijk. */
function prettyPlate(plate) {
  // Val terug op het ruwe kenteken; RDW kent vele sidecodes, dus houd het simpel.
  return plate;
}

function setStatus(html, isError = false) {
  statusEl.innerHTML = html
    ? `<span class="${isError ? "error" : ""}">${html}</span>`
    : "";
}

function setLoading(loading) {
  submitBtn.disabled = loading;
  submitBtn.textContent = loading ? "Bezig…" : "Zoek";
  if (loading) setStatus('<span class="spinner"></span>Gegevens ophalen…');
}

async function fetchJson(url, plate) {
  const res = await fetch(`${url}?kenteken=${encodeURIComponent(plate)}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`RDW gaf status ${res.status}`);
  return res.json();
}

/** Definieer de velden die we tonen, in volgorde. */
function buildFields(v, fuel) {
  const brandstof = fuel && fuel.length
    ? [...new Set(fuel.map((f) => f.brandstof_omschrijving).filter(Boolean))].join(", ")
    : null;

  return [
    ["Voertuigsoort", v.voertuigsoort],
    ["Merk", v.merk],
    ["Model / handelsbenaming", v.handelsbenaming],
    ["Brandstof", brandstof],
    ["Kleur", [v.eerste_kleur, v.tweede_kleur].filter((c) => c && c !== "N.v.t.").join(" / ")],
    ["Inrichting", v.inrichting],
    ["Aantal zitplaatsen", v.aantal_zitplaatsen],
    ["Aantal deuren", v.aantal_deuren],
    ["Cilinderinhoud", formatNumber(v.cilinderinhoud, " cc")],
    ["Massa ledig voertuig", formatNumber(v.massa_ledig_voertuig, " kg")],
    ["Toegestane max. massa", formatNumber(v.toegestane_maximum_massa_voertuig, " kg")],
    ["Datum eerste toelating", formatDate(v.datum_eerste_toelating)],
    ["Eerste toelating NL", formatDate(v.datum_eerste_tenaamstelling_in_nederland)],
    ["APK geldig tot", formatDate(v.vervaldatum_apk)],
    ["Catalogusprijs", formatEuro(v.catalogusprijs)],
    ["WAM verzekerd", v.wam_verzekerd === "Ja" ? "Ja" : v.wam_verzekerd === "Nee" ? "Nee" : v.wam_verzekerd],
    ["Tenaamstelling", formatDate(v.datum_tenaamstelling)],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
}

function renderResult(v, fuel, plate) {
  const naam = [v.merk, v.handelsbenaming].filter(Boolean).join(" ") || "Voertuig";
  titleEl.textContent = naam;
  plateEl.textContent = prettyPlate(plate);

  gridEl.innerHTML = "";
  for (const [label, value] of buildFields(v, fuel)) {
    const wrap = document.createElement("div");
    wrap.className = "item";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    wrap.append(dt, dd);
    gridEl.appendChild(wrap);
  }

  sourceLink.href = `https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken=${encodeURIComponent(plate)}`;
  resultEl.hidden = false;
}

async function lookup(rawPlate) {
  const plate = normalizePlate(rawPlate);
  resultEl.hidden = true;

  if (plate.length < 4) {
    setStatus("Voer een geldig kenteken in (minimaal 4 tekens).", true);
    return;
  }

  setLoading(true);
  try {
    const [vehicles, fuel] = await Promise.all([
      fetchJson(VEHICLE_URL, plate),
      fetchJson(FUEL_URL, plate).catch(() => []),
    ]);

    if (!vehicles.length) {
      setStatus(`Geen voertuig gevonden voor kenteken <strong>${plate}</strong>.`, true);
      return;
    }

    setStatus("");
    renderResult(vehicles[0], fuel, plate);
  } catch (err) {
    setStatus(
      `Er ging iets mis bij het ophalen van de gegevens. Probeer het later opnieuw.<br><small>${err.message}</small>`,
      true
    );
  } finally {
    setLoading(false);
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  lookup(input.value);
});

// Laat de gebruiker via de URL een kenteken meegeven: ?kenteken=XX999X
const params = new URLSearchParams(location.search);
const preset = params.get("kenteken") || params.get("plate");
if (preset) {
  input.value = normalizePlate(preset);
  lookup(preset);
}

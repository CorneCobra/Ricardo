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

// Inspectie-formulier
const inspectionEl = document.getElementById("inspection");
const inspectionForm = document.getElementById("inspection-form");
const inspPlateEl = document.getElementById("insp-plate");
const inspApkEl = document.getElementById("insp-apk");
const fotoInput = document.getElementById("fotos");
const fotoPreview = document.getElementById("foto-preview");
const velgFotoInput = document.getElementById("velg-fotos");
const velgFotoPreview = document.getElementById("velg-foto-preview");
const pdfBtn = document.getElementById("pdf-btn");
const pdfStatus = document.getElementById("pdf-status");

// Huidige staat, gedeeld tussen lookup en inspectie/PDF.
let currentVehicle = null;
let currentPlate = "";
let currentFuel = [];
const photos = []; // algemene foto's: { dataUrl, w, h }
const velgPhotos = []; // foto's van velgschade

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

/*
 * Nederlandse kenteken-sidecodes: elke signature (X = letter, D = cijfer)
 * bepaalt waar de streepjes komen (groepslengtes).
 */
const SIDECODES = {
  XXDDDD: [2, 2, 2], // AB-12-34
  DDDDXX: [2, 2, 2], // 12-34-AB
  DDXXDD: [2, 2, 2], // 12-AB-34
  XXDDXX: [2, 2, 2], // AB-12-CD
  XXXXDD: [2, 2, 2], // AB-CD-12
  DDXXXX: [2, 2, 2], // 12-AB-CD
  DDXXXD: [2, 3, 1], // 12-ABC-3
  DXXXDD: [1, 3, 2], // 1-ABC-23
  XXDDDX: [2, 3, 1], // AB-123-C
  XDDDXX: [1, 3, 2], // A-123-BC
  XXXDDX: [3, 2, 1], // ABC-12-D
  XDDXXX: [1, 2, 3], // A-12-BCD
  DXXDDD: [1, 2, 3], // 1-AB-234
  DDDXXD: [3, 2, 1], // 123-AB-4
};

/** Formatteer een kenteken in Nederlandse notatie met streepjes. */
function formatDutchPlate(raw) {
  const plate = normalizePlate(raw);
  if (plate.length !== 6) return plate;
  const signature = plate.replace(/[A-Z]/g, "X").replace(/[0-9]/g, "D");
  const groups = SIDECODES[signature];
  if (!groups) return plate;
  const parts = [];
  let i = 0;
  for (const len of groups) {
    parts.push(plate.slice(i, i + len));
    i += len;
  }
  return parts.join("-");
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
  plateEl.textContent = formatDutchPlate(plate);

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

  setupInspection(v, fuel, plate);
}

/** Bepaal op basis van de APK-vervaldatum of de auto APK nodig heeft. */
function deriveApkStatus(vervaldatum) {
  if (!vervaldatum) return "Onbekend (geen APK-datum bij de RDW)";
  const s = String(vervaldatum).slice(0, 8);
  if (!/^\d{8}$/.test(s)) return "Onbekend";
  const expiry = new Date(
    Number(s.slice(0, 4)),
    Number(s.slice(4, 6)) - 1,
    Number(s.slice(6, 8))
  );
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const pretty = formatDate(vervaldatum);
  const soon = new Date(today);
  soon.setDate(soon.getDate() + 56); // ~8 weken

  if (expiry < today) return `Ja — APK verlopen (was geldig tot ${pretty})`;
  if (expiry <= soon) return `Binnenkort — verloopt op ${pretty}`;
  return `Nee — geldig tot ${pretty}`;
}

/** Toon en initialiseer het inspectie-formulier na een geslaagde lookup. */
function setupInspection(v, fuel, plate) {
  currentVehicle = v;
  currentFuel = fuel;
  currentPlate = plate;
  inspPlateEl.value = formatDutchPlate(plate);
  inspApkEl.value = deriveApkStatus(v.vervaldatum_apk);
  inspectionEl.hidden = false;
  pdfStatus.textContent = "";
}

async function lookup(rawPlate) {
  const plate = normalizePlate(rawPlate);
  resultEl.hidden = true;
  inspectionEl.hidden = true;

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

// Live formatteren van het kenteken tijdens het typen.
input.addEventListener("input", () => {
  const formatted = formatDutchPlate(input.value);
  if (formatted !== input.value) input.value = formatted;
});

/* ---- Voorwaardelijke tekstvelden (schade / onderhoud) ---- */
function toggleConditional(name, detailId) {
  const detail = document.getElementById(detailId);
  const update = () => {
    const chosen = inspectionForm.querySelector(`input[name="${name}"]:checked`);
    detail.hidden = !(chosen && chosen.value === "Ja");
  };
  inspectionForm
    .querySelectorAll(`input[name="${name}"]`)
    .forEach((radio) => radio.addEventListener("change", update));
  update();
}
toggleConditional("schade", "schade-detail");
toggleConditional("velgschade", "velgschade-detail");
toggleConditional("onderhoud", "onderhoud-detail");

/* ---- Foto's: inlezen, verkleinen, preview ---- */
const MAX_EDGE = 1600;

function readAndScale(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Kan bestand niet lezen"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("Kan afbeelding niet laden"));
      img.onload = () => {
        let { width, height } = img;
        if (width > MAX_EDGE || height > MAX_EDGE) {
          const scale = MAX_EDGE / Math.max(width, height);
          width = Math.round(width * scale);
          height = Math.round(height * scale);
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        canvas.getContext("2d").drawImage(img, 0, 0, width, height);
        resolve({ dataUrl: canvas.toDataURL("image/jpeg", 0.8), w: width, h: height });
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

/* Koppel een bestand-invoer aan een fotolijst + preview (herbruikbaar). */
function setupPhotoInput(inputEl, previewEl, store) {
  const render = () => {
    previewEl.innerHTML = "";
    store.forEach((photo, index) => {
      const thumb = document.createElement("div");
      thumb.className = "foto-thumb";
      const img = document.createElement("img");
      img.src = photo.dataUrl;
      img.alt = `Foto ${index + 1}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.setAttribute("aria-label", `Verwijder foto ${index + 1}`);
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        store.splice(index, 1);
        render();
      });
      thumb.append(img, remove);
      previewEl.appendChild(thumb);
    });
  };
  inputEl.addEventListener("change", async () => {
    for (const file of Array.from(inputEl.files || [])) {
      if (!file.type.startsWith("image/")) continue;
      try {
        store.push(await readAndScale(file));
      } catch {
        /* sla onleesbare bestanden over */
      }
    }
    inputEl.value = ""; // sta toe dezelfde foto opnieuw te kiezen
    render();
  });
}

setupPhotoInput(fotoInput, fotoPreview, photos);
setupPhotoInput(velgFotoInput, velgFotoPreview, velgPhotos);

/* ---- PDF genereren ---- */
function collectAnswers() {
  const val = (name) => {
    const el = inspectionForm.querySelector(`[name="${name}"]:checked, [name="${name}"]:not([type=radio])`);
    return el ? el.value.trim() : "";
  };
  return {
    schade: val("schade"),
    schade_omschrijving: val("schade_omschrijving"),
    velgschade: val("velgschade"),
    velgschade_omschrijving: val("velgschade_omschrijving"),
    onderhoud: val("onderhoud"),
    onderhoud_omschrijving: val("onderhoud_omschrijving"),
    laatste_onderhoud: val("laatste_onderhoud"),
    km_onderhoud: val("km_onderhoud"),
    laadkabel: val("laadkabel"),
    slotbout: val("slotbout"),
    airco: val("airco"),
    profiel_voor: val("profiel_voor"),
    profiel_achter: val("profiel_achter"),
  };
}

function buildPdf() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 15;
  const contentW = pageW - margin * 2;
  let y = margin;

  const ensureSpace = (needed) => {
    if (y + needed > pageH - margin) {
      doc.addPage();
      y = margin;
    }
  };
  const heading = (text) => {
    ensureSpace(12);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(13);
    doc.text(text, margin, y);
    y += 6;
    doc.setDrawColor(200);
    doc.line(margin, y, pageW - margin, y);
    y += 5;
  };
  const row = (label, value) => {
    if (value === undefined || value === null || value === "") return;
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    const labelW = 55;
    ensureSpace(6);
    doc.text(String(label), margin, y);
    doc.setFont("helvetica", "normal");
    const lines = doc.splitTextToSize(String(value), contentW - labelW);
    doc.text(lines, margin + labelW, y);
    y += Math.max(6, lines.length * 5);
  };

  // Titel
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("Keuringsrapport voertuig", margin, y);
  y += 8;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(100);
  const now = new Date();
  const stamp = now.toLocaleString("nl-NL", { dateStyle: "long", timeStyle: "short" });
  doc.text(`Kenteken: ${formatDutchPlate(currentPlate)}   •   Opgesteld: ${stamp}`, margin, y);
  doc.setTextColor(0);
  y += 8;

  // Voertuiggegevens (RDW)
  heading("Voertuiggegevens (RDW)");
  for (const [label, value] of buildFields(currentVehicle, currentFuel)) {
    row(label, value);
  }

  // Keuring / inspectie
  y += 3;
  heading("Keuring / inname");
  const a = collectAnswers();
  row("APK nodig?", inspApkEl.value);
  row("Schade?", a.schade);
  if (a.schade === "Ja") row("Omschrijving schade", a.schade_omschrijving || "—");
  row("Velgschade?", a.velgschade);
  if (a.velgschade === "Ja") row("Omschrijving velgschade", a.velgschade_omschrijving || "—");
  row("Onderhoud nodig?", a.onderhoud);
  if (a.onderhoud === "Ja") row("Welk onderhoud", a.onderhoud_omschrijving || "—");
  row("Laatste onderhoud", a.laatste_onderhoud ? formatDate(a.laatste_onderhoud.replace(/-/g, "")) : "—");
  row("Kilometerstand laatste onderhoud", a.km_onderhoud ? `${formatNumber(a.km_onderhoud)} km` : "—");
  row("Laadkabel aanwezig?", a.laadkabel);
  row("Slotbout aanwezig?", a.slotbout);
  row("Airco werkt?", a.airco);
  row("Profiel voorbanden", a.profiel_voor ? `${a.profiel_voor} mm` : "—");
  row("Profiel achterbanden", a.profiel_achter ? `${a.profiel_achter} mm` : "—");

  // Foto's — 6 per pagina (2 kolommen × 3 rijen).
  const photoGrid = (title, list) => {
    if (!list.length) return;
    const cols = 2;
    const rows = 3;
    const gap = 6;
    const cellW = (contentW - gap * (cols - 1)) / cols;
    // Start elke fotosectie op een nieuwe pagina, zodat 6 foto's op vol
    // formaat passen (2 kolommen × 3 rijen).
    doc.addPage();
    y = margin;
    heading(`${title} (${list.length})`);
    let gridTop = y;
    const perPage = cols * rows;
    const cellHFor = (top) => (pageH - margin - top - gap * (rows - 1)) / rows;
    let cellH = cellHFor(gridTop);

    list.forEach((photo, i) => {
      const cell = i % perPage;
      if (i > 0 && cell === 0) {
        doc.addPage();
        gridTop = margin;
        cellH = cellHFor(gridTop);
      }
      const col = cell % cols;
      const rowIdx = Math.floor(cell / cols);
      const cx = margin + col * (cellW + gap);
      const cy = gridTop + rowIdx * (cellH + gap);
      let w = cellW;
      let h = (photo.h / photo.w) * w;
      if (h > cellH) {
        h = cellH;
        w = (photo.w / photo.h) * h;
      }
      doc.addImage(photo.dataUrl, "JPEG", cx + (cellW - w) / 2, cy + (cellH - h) / 2, w, h);
    });

    // Zet y onder de laatst gebruikte rij.
    const onLastPage = ((list.length - 1) % perPage) + 1;
    const rowsUsed = Math.ceil(onLastPage / cols);
    y = gridTop + rowsUsed * cellH + (rowsUsed - 1) * gap;
  };

  photoGrid("Foto's", photos);
  if (a.velgschade === "Ja") photoGrid("Foto's velgschade", velgPhotos);

  // Voettekst met disclaimer
  doc.setFontSize(8);
  doc.setTextColor(120);
  const disclaimer =
    "Voertuiggegevens afkomstig van de RDW open data. Aan dit rapport kunnen geen rechten worden ontleend.";
  ensureSpace(6);
  doc.text(doc.splitTextToSize(disclaimer, contentW), margin, pageH - margin + 2);

  return doc;
}

inspectionForm.addEventListener("submit", (e) => {
  e.preventDefault();
  if (!currentVehicle) {
    pdfStatus.innerHTML = '<span class="error">Zoek eerst een kenteken op.</span>';
    return;
  }
  if (!window.jspdf || !window.jspdf.jsPDF) {
    pdfStatus.innerHTML = '<span class="error">PDF-bibliotheek kon niet worden geladen.</span>';
    return;
  }
  pdfBtn.disabled = true;
  pdfStatus.textContent = "PDF wordt gemaakt…";
  try {
    const doc = buildPdf();
    doc.save(`keuring-${normalizePlate(currentPlate) || "voertuig"}.pdf`);
    pdfStatus.textContent = "PDF gedownload.";
  } catch (err) {
    pdfStatus.innerHTML = `<span class="error">Er ging iets mis bij het maken van de PDF. ${err.message}</span>`;
  } finally {
    pdfBtn.disabled = false;
  }
});

// Laat de gebruiker via de URL een kenteken meegeven: ?kenteken=XX999X
const params = new URLSearchParams(location.search);
const preset = params.get("kenteken") || params.get("plate");
if (preset) {
  input.value = formatDutchPlate(preset);
  lookup(preset);
}

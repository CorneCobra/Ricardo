/*
 * Opmaak-hulpjes voor Nederlandse weergave van geld, datum, tijd en telefoon.
 * Bedragen gaan intern altijd in hele centen (integer) rond; hier wordt pas
 * omgerekend naar euro's voor de weergave.
 */

const euroOpmaak = new Intl.NumberFormat("nl-NL", {
  style: "currency",
  currency: "EUR",
});

const dagOpmaak = new Intl.DateTimeFormat("nl-NL", {
  weekday: "long",
  day: "numeric",
  month: "long",
});

const dagKortOpmaak = new Intl.DateTimeFormat("nl-NL", {
  weekday: "short",
  day: "numeric",
  month: "short",
});

const maandOpmaak = new Intl.DateTimeFormat("nl-NL", {
  month: "long",
  year: "numeric",
});

/** 4550 -> "€ 45,00" */
export function euro(bedragCent) {
  return euroOpmaak.format((bedragCent || 0) / 100);
}

/**
 * "45", "45,50", "€ 45.50" -> 4550. Geeft null bij een onbruikbare invoer,
 * zodat de aanroeper zelf een nette foutmelding kan tonen.
 */
export function naarCent(invoer) {
  const schoon = String(invoer || "")
    .replace(/[€\s]/g, "")
    .replace(",", ".");
  if (!schoon || !/^\d+(\.\d{1,2})?$/.test(schoon)) return null;
  return Math.round(Number(schoon) * 100);
}

/** "2026-09-20" (lokale dag van vandaag) */
export function vandaagISO() {
  return naarISODatum(new Date());
}

/** Date -> "2026-09-20", zonder tijdzone-verschuiving. */
export function naarISODatum(datum) {
  const m = String(datum.getMonth() + 1).padStart(2, "0");
  const d = String(datum.getDate()).padStart(2, "0");
  return `${datum.getFullYear()}-${m}-${d}`;
}

/** "2026-09-20T10:30" -> "2026-09-20" */
export function datumVan(start) {
  return String(start).slice(0, 10);
}

/** "2026-09-20T10:30" -> "10:30" */
export function tijdVan(start) {
  return String(start).slice(11, 16);
}

/** "2026-09-20" -> Date op middernacht lokale tijd. */
export function alsDatum(isoDatum) {
  const [j, m, d] = String(isoDatum).slice(0, 10).split("-").map(Number);
  return new Date(j, m - 1, d);
}

/** "Vandaag", "Morgen", "Gisteren" of "vrijdag 19 september". */
export function dagLabel(isoDatum) {
  const verschil = dagenVerschil(vandaagISO(), isoDatum);
  if (verschil === 0) return "Vandaag";
  if (verschil === 1) return "Morgen";
  if (verschil === -1) return "Gisteren";
  return dagOpmaak.format(alsDatum(isoDatum));
}

/** "vr 19 sep" */
export function dagKort(isoDatum) {
  return dagKortOpmaak.format(alsDatum(isoDatum));
}

/** "september 2026" */
export function maandLabel(isoDatum) {
  return maandOpmaak.format(alsDatum(isoDatum));
}

/** Aantal hele dagen tussen twee ISO-datums (b - a). */
export function dagenVerschil(a, b) {
  const msPerDag = 24 * 60 * 60 * 1000;
  return Math.round((alsDatum(b) - alsDatum(a)) / msPerDag);
}

/** 90 -> "1,5 uur", 45 -> "45 min" */
export function duurLabel(minuten) {
  if (!minuten) return "";
  if (minuten < 60) return `${minuten} min`;
  const uren = minuten / 60;
  return `${getal(uren)} uur`;
}

/** Getal in Nederlandse notatie, zonder onnodige decimalen. */
export function getal(waarde, decimalen = 1) {
  return new Intl.NumberFormat("nl-NL", {
    maximumFractionDigits: decimalen,
  }).format(waarde || 0);
}

/** "06 12 34 56 78" -> "tel:+31612345678" */
export function telHref(telefoon) {
  const cijfers = String(telefoon || "").replace(/[^\d+]/g, "");
  if (cijfers.startsWith("06")) return `tel:+31${cijfers.slice(1)}`;
  return `tel:${cijfers}`;
}

/** Voorkomt dat vrije tekst als HTML wordt uitgevoerd. */
export function veilig(tekst) {
  return String(tekst ?? "").replace(/[&<>"']/g, (teken) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[teken]);
}

/** "10:30" -> 630 minuten sinds middernacht. */
export function minutenVan(tijd) {
  const [u, m] = String(tijd).slice(0, 5).split(":").map(Number);
  return u * 60 + m;
}

/** 630 -> "10:30" */
export function tijdVanMinuten(minuten) {
  const m = Math.max(0, Math.round(minuten));
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/** "10:00 – 11:00" voor een afspraak. */
export function tijdvak(start, duurMin) {
  const begin = minutenVan(tijdVan(start));
  return `${tijdVan(start)} – ${tijdVanMinuten(begin + (duurMin || 0))}`;
}

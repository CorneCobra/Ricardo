/*
 * De volledige state van de app, in het geheugen. Views lezen en schrijven
 * uitsluitend via deze module; na elke wijziging krijgen de abonnees een
 * seintje zodat het actieve tabblad opnieuw getekend wordt.
 */

import { maakStartData } from "./data.js";
import { datumVan, vandaagISO } from "./format.js";

const state = maakStartData();
const abonnees = new Set();

function melden() {
  abonnees.forEach((fn) => fn());
}

function nieuwId() {
  return crypto.randomUUID();
}

/** Roep fn aan na elke wijziging. Geeft een functie terug om te stoppen. */
export function subscribe(fn) {
  abonnees.add(fn);
  return () => abonnees.delete(fn);
}

/* ---------------------------------------------------------------- klanten */

export function getKlanten() {
  return [...state.klanten].sort((a, b) => a.naam.localeCompare(b.naam, "nl"));
}

export function getKlant(id) {
  return state.klanten.find((k) => k.id === id) || null;
}

export function voegKlantToe(velden) {
  const klant = {
    id: nieuwId(),
    naam: "",
    telefoon: "",
    adres: "",
    plaats: "",
    afstandKm: 0,
    notitie: "",
    ...velden,
  };
  state.klanten.push(klant);
  melden();
  return klant;
}

export function wijzigKlant(id, velden) {
  const klant = getKlant(id);
  if (!klant) return null;
  Object.assign(klant, velden);
  melden();
  return klant;
}

/** Volledig adres van een klant, zoals het in een afspraak terechtkomt. */
export function adresVanKlant(klant) {
  if (!klant) return "";
  return [klant.adres, klant.plaats].filter(Boolean).join(", ");
}

/* -------------------------------------------------------------- afspraken */

/** Alle afspraken, oplopend op tijd. Optioneel gefilterd op datumbereik. */
export function getAfspraken({ vanaf, tot } = {}) {
  return state.afspraken
    .filter((a) => {
      const datum = datumVan(a.start);
      if (vanaf && datum < vanaf) return false;
      if (tot && datum > tot) return false;
      return true;
    })
    .sort((a, b) => a.start.localeCompare(b.start));
}

/** Alles vanaf vandaag 00:00. */
export function getKomendeAfspraken() {
  return getAfspraken({ vanaf: vandaagISO() });
}

/** Alles vóór vandaag, nieuwste eerst. */
export function getAfgelopenAfspraken() {
  return getAfspraken()
    .filter((a) => datumVan(a.start) < vandaagISO())
    .reverse();
}

export function getAfspraak(id) {
  return state.afspraken.find((a) => a.id === id) || null;
}

export function voegAfspraakToe(velden) {
  const afspraak = {
    id: nieuwId(),
    klantId: null,
    start: "",
    duurMin: 60,
    locatie: "",
    behandeling: "",
    omzet: null,
    verplaatstVan: null,
    ...velden,
  };
  state.afspraken.push(afspraak);
  melden();
  return afspraak;
}

export function wijzigAfspraak(id, velden) {
  const afspraak = getAfspraak(id);
  if (!afspraak) return null;
  Object.assign(afspraak, velden);
  melden();
  return afspraak;
}

/** Zet een nieuwe starttijd en onthoudt waar de afspraak vandaan kwam. */
export function verplaatsAfspraak(id, nieuweStart) {
  const afspraak = getAfspraak(id);
  if (!afspraak || nieuweStart === afspraak.start) return afspraak;
  afspraak.verplaatstVan = afspraak.start;
  afspraak.start = nieuweStart;
  melden();
  return afspraak;
}

export function verwijderAfspraak(id) {
  const index = state.afspraken.findIndex((a) => a.id === id);
  if (index === -1) return false;
  state.afspraken.splice(index, 1);
  melden();
  return true;
}

/**
 * Omzet van een afspraak vastleggen of corrigeren.
 * methode is alleen gevuld wanneer er ook echt betaald is.
 */
export function zetOmzet(afspraakId, { bedragCent, betaald, methode }) {
  const afspraak = getAfspraak(afspraakId);
  if (!afspraak) return null;
  afspraak.omzet = {
    bedragCent,
    betaald: Boolean(betaald),
    methode: betaald ? methode : null,
  };
  melden();
  return afspraak;
}

/* ------------------------------------------------------------- stortingen */

export function getStortingen() {
  return [...state.stortingen].sort((a, b) => b.datum.localeCompare(a.datum));
}

export function voegStortingToe({ datum, bedragCent }) {
  const storting = { id: nieuwId(), datum, bedragCent };
  state.stortingen.push(storting);
  melden();
  return storting;
}

export function verwijderStorting(id) {
  const index = state.stortingen.findIndex((s) => s.id === id);
  if (index === -1) return false;
  state.stortingen.splice(index, 1);
  melden();
  return true;
}

/* ---------------------------------------------------------- km en uren */

export function getDagen() {
  return [...state.dagen].sort((a, b) => b.datum.localeCompare(a.datum));
}

export function getDag(datum) {
  return state.dagen.find((d) => d.datum === datum) || null;
}

/** Eén registratie per datum: bestaat die al, dan wordt hij bijgewerkt. */
export function zetDag({ datum, km, uren }) {
  const bestaand = getDag(datum);
  if (bestaand) {
    bestaand.km = km;
    bestaand.uren = uren;
    melden();
    return bestaand;
  }
  const dag = { id: nieuwId(), datum, km, uren };
  state.dagen.push(dag);
  melden();
  return dag;
}

export function verwijderDag(id) {
  const index = state.dagen.findIndex((d) => d.id === id);
  if (index === -1) return false;
  state.dagen.splice(index, 1);
  melden();
  return true;
}

/**
 * Voorstel voor de dagkilometers: de vaste afstand (retour) van elke klant
 * met een afspraak op die dag. Twee afspraken bij dezelfde klant tellen één
 * keer — dat is immers één rit heen en terug.
 */
export function voorgesteldeKm(datum) {
  const klantIds = new Set(
    getAfspraken({ vanaf: datum, tot: datum }).map((a) => a.klantId),
  );
  let totaal = 0;
  klantIds.forEach((id) => {
    const klant = getKlant(id);
    if (klant) totaal += Number(klant.afstandKm) || 0;
  });
  return Math.round(totaal * 10) / 10;
}

/** Aantal afspraken op een dag — voor de toelichting bij het km-voorstel. */
export function aantalAfsprakenOp(datum) {
  return getAfspraken({ vanaf: datum, tot: datum }).length;
}

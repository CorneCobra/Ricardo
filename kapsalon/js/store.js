/*
 * De volledige state van de app, in het geheugen. Views lezen en schrijven
 * uitsluitend via deze module; na elke wijziging krijgen de abonnees een
 * seintje zodat het actieve tabblad opnieuw getekend wordt.
 */

import { maakStartData } from "./data.js";
import { datumVan, minutenVan, tijdVan, tijdVanMinuten, vandaagISO } from "./format.js";

const state = maakStartData();
const abonnees = new Set();

/** Dagvenster waarbinnen de agenda en de vrije plekken worden getoond. */
export const DAG_START = 8 * 60; // 08:00
export const DAG_EINDE = 20 * 60; // 20:00

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

/** De plaats van een klant; die vult standaard de locatie van een afspraak. */
export function plaatsVanKlant(klant) {
  return klant?.plaats || "";
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

/** De afspraken van één dag, oplopend op tijd. */
export function afsprakenOp(datum) {
  return getAfspraken({ vanaf: datum, tot: datum });
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
    notitie: "",
    omzet: null,
    verplaatstVan: null,
    ...velden,
  };
  state.afspraken.push(afspraak);
  herberekenAfsluitingen(datumVan(afspraak.start));
  melden();
  return afspraak;
}

export function wijzigAfspraak(id, velden) {
  const afspraak = getAfspraak(id);
  if (!afspraak) return null;
  const oudeDatum = datumVan(afspraak.start);
  Object.assign(afspraak, velden);
  herberekenAfsluitingen(oudeDatum, datumVan(afspraak.start));
  melden();
  return afspraak;
}

/** Zet een nieuwe starttijd en onthoudt waar de afspraak vandaan kwam. */
export function verplaatsAfspraak(id, nieuweStart) {
  const afspraak = getAfspraak(id);
  if (!afspraak || nieuweStart === afspraak.start) return afspraak;
  const oudeDatum = datumVan(afspraak.start);
  afspraak.verplaatstVan = afspraak.start;
  afspraak.start = nieuweStart;
  // De omzet hangt aan de afspraak en verhuist dus mee; beide dagen opnieuw
  // doorrekenen zodat een afgesloten dag blijft kloppen.
  herberekenAfsluitingen(oudeDatum, datumVan(nieuweStart));
  melden();
  return afspraak;
}

export function verwijderAfspraak(id) {
  const index = state.afspraken.findIndex((a) => a.id === id);
  if (index === -1) return false;
  const datum = datumVan(state.afspraken[index].start);
  state.afspraken.splice(index, 1);
  herberekenAfsluitingen(datum);
  melden();
  return true;
}

/**
 * Omzet van een afspraak vastleggen of corrigeren. bedragCent is de
 * behandeling zelf; producten zijn losse verkopen ({ omschrijving,
 * bedragCent }) die bij dezelfde afspraak horen. methode is alleen gevuld
 * wanneer er ook echt betaald is.
 */
export function zetOmzet(afspraakId, { bedragCent, producten = [], betaald, methode }) {
  const afspraak = getAfspraak(afspraakId);
  if (!afspraak) return null;
  afspraak.omzet = {
    bedragCent: Number(bedragCent) || 0,
    producten: producten.map((p) => ({
      id: p.id || nieuwId(),
      omschrijving: p.omschrijving,
      bedragCent: Number(p.bedragCent) || 0,
    })),
    betaald: Boolean(betaald),
    methode: betaald ? methode : null,
  };
  herberekenAfsluitingen(datumVan(afspraak.start));
  melden();
  return afspraak;
}

/** Wat de verkochte producten bij een afspraak samen opbrengen. */
export function productenTotaal(omzet) {
  return (omzet?.producten || []).reduce((som, p) => som + (p.bedragCent || 0), 0);
}

/** Behandeling plus verkochte producten. */
export function omzetTotaal(omzet) {
  if (!omzet) return 0;
  return (omzet.bedragCent || 0) + productenTotaal(omzet);
}

/**
 * De laatste notities van deze klant vóór een bepaalde afspraak — zodat je
 * bij het knippen ziet wat je de vorige keren hebt opgeschreven.
 */
export function vorigeNotities(klantId, voorStart, aantal = 3) {
  return getAfspraken()
    .filter(
      (a) =>
        a.klantId === klantId &&
        a.start < voorStart &&
        (a.notitie || "").trim() !== "",
    )
    .reverse()
    .slice(0, aantal);
}

/* ------------------------------------------------------- agenda en ruimte */

/** Begin- en eindminuut van een afspraak binnen zijn eigen dag. */
export function tijdvakVan(afspraak) {
  const begin = minutenVan(tijdVan(afspraak.start));
  return { begin, einde: begin + (Number(afspraak.duurMin) || 0) };
}

/**
 * De afspraken die botsen met een voorgenomen tijdstip. negeerId slaat de
 * afspraak zelf over, zodat verplaatsen niet met zichzelf in conflict komt.
 */
export function overlapMet({ datum, tijd, duurMin, negeerId = null }) {
  const begin = minutenVan(tijd);
  const einde = begin + (Number(duurMin) || 0);
  return afsprakenOp(datum).filter((a) => {
    if (a.id === negeerId) return false;
    const vak = tijdvakVan(a);
    return begin < vak.einde && einde > vak.begin;
  });
}

/**
 * Vrije starttijden op een dag waar een afspraak van duurMin minuten past.
 * Loopt het dagvenster af in stappen van een kwartier.
 */
export function vrijeSlots(datum, duurMin, { negeerId = null, maximaal = 6 } = {}) {
  const duur = Number(duurMin) || 60;
  const slots = [];
  for (let m = DAG_START; m + duur <= DAG_EINDE; m += 15) {
    const tijd = tijdVanMinuten(m);
    if (overlapMet({ datum, tijd, duurMin: duur, negeerId }).length === 0) {
      slots.push(tijd);
    }
  }
  if (slots.length <= maximaal) return slots;

  // Spreid de suggesties over de dag in plaats van zes keer hetzelfde uur.
  const stap = Math.ceil(slots.length / maximaal);
  return slots.filter((_, i) => i % stap === 0).slice(0, maximaal);
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

/* ----------------------------------------------------------------- kosten */

export function getKosten({ maand } = {}) {
  return state.kosten
    .filter((k) => !maand || k.datum.startsWith(maand))
    .sort((a, b) => b.datum.localeCompare(a.datum));
}

export function voegKostenToe({ datum, omschrijving, bedragCent, bon = null }) {
  const post = { id: nieuwId(), datum, omschrijving, bedragCent, bon };
  state.kosten.push(post);
  melden();
  return post;
}

export function verwijderKosten(id) {
  const index = state.kosten.findIndex((k) => k.id === id);
  if (index === -1) return false;
  state.kosten.splice(index, 1);
  melden();
  return true;
}

/* ------------------------------------------------------------ maandcijfers */

/**
 * Alles van één maand ("2026-09") op een rij: omzet uit de afspraken van die
 * maand, de kosten, de winst (alle omzet min kosten, dus inclusief wat nog
 * binnen moet komen) en wat er nog te ontvangen is. Kilometers en uren komen
 * uit de dagen die je hebt afgesloten.
 */
export function maandTotalen(maand) {
  let omzetCent = 0;
  let cashCent = 0;
  let bankCent = 0;
  let openCent = 0;
  let productenCent = 0;
  let aantalAfspraken = 0;

  getAfspraken()
    .filter((a) => datumVan(a.start).startsWith(maand))
    .forEach((a) => {
      aantalAfspraken += 1;
      if (!a.omzet) return;
      const totaal = omzetTotaal(a.omzet);
      productenCent += productenTotaal(a.omzet);
      omzetCent += totaal;
      if (!a.omzet.betaald) openCent += totaal;
      else if (a.omzet.methode === "cash") cashCent += totaal;
      else bankCent += totaal;
    });

  const kostenCent = getKosten({ maand }).reduce((som, k) => som + k.bedragCent, 0);
  const gestortCent = state.stortingen
    .filter((s) => s.datum.startsWith(maand))
    .reduce((som, s) => som + s.bedragCent, 0);

  const dagen = state.afsluitingen.filter((a) => a.datum.startsWith(maand));
  const km = dagen.reduce((som, d) => som + (Number(d.km) || 0), 0);
  const uren = dagen.reduce((som, d) => som + (Number(d.uren) || 0), 0);

  return {
    maand,
    aantalAfspraken,
    omzetCent,
    productenCent,
    cashCent,
    bankCent,
    openCent,
    kostenCent,
    winstCent: omzetCent - kostenCent,
    gestortCent,
    afgeslotenDagen: dagen.length,
    km: Math.round(km * 10) / 10,
    uren: Math.round(uren * 100) / 100,
  };
}

/* ----------------------------------------------------------- dagafsluiting */

/**
 * Alles wat een dag heeft opgeleverd, berekend uit de afspraken van die dag:
 * omzet (gesplitst naar cash, bank en nog openstaand), de gereden kilometers
 * en de gewerkte uren. Dezelfde klant twee keer op een dag telt als één rit.
 */
export function dagTotalen(datum) {
  const afspraken = afsprakenOp(datum);
  const klantIds = new Set();
  let minuten = 0;
  let omzetCent = 0;
  let cashCent = 0;
  let bankCent = 0;
  let openCent = 0;
  let productenCent = 0;
  let zonderOmzet = 0;

  afspraken.forEach((a) => {
    klantIds.add(a.klantId);
    minuten += Number(a.duurMin) || 0;
    if (!a.omzet) {
      zonderOmzet += 1;
      return;
    }
    const totaal = omzetTotaal(a.omzet);
    productenCent += productenTotaal(a.omzet);
    omzetCent += totaal;
    if (!a.omzet.betaald) openCent += totaal;
    else if (a.omzet.methode === "cash") cashCent += totaal;
    else bankCent += totaal;
  });

  let km = 0;
  klantIds.forEach((id) => {
    const klant = getKlant(id);
    if (klant) km += Number(klant.afstandKm) || 0;
  });

  return {
    datum,
    aantalAfspraken: afspraken.length,
    zonderOmzet,
    km: Math.round(km * 10) / 10,
    uren: Math.round((minuten / 60) * 100) / 100,
    omzetCent,
    productenCent,
    cashCent,
    bankCent,
    openCent,
  };
}

/**
 * Dagen die nog afgesloten moeten worden: alle dagen tot en met vandaag met
 * minstens één afspraak waarvoor nog geen afsluiting bestaat. Nieuwste eerst.
 */
export function openDagen() {
  const vandaag = vandaagISO();
  const datums = new Set(
    getAfspraken({ tot: vandaag }).map((a) => datumVan(a.start)),
  );
  return [...datums]
    .filter((d) => !getAfsluiting(d))
    .sort((a, b) => b.localeCompare(a))
    .map((d) => dagTotalen(d));
}

export function getAfsluitingen() {
  return [...state.afsluitingen].sort((a, b) => b.datum.localeCompare(a.datum));
}

export function getAfsluiting(datum) {
  return state.afsluitingen.find((a) => a.datum === datum) || null;
}

/**
 * Sluit een dag af: de berekende totalen worden vastgelegd, met de
 * kilometers en uren zoals ze op dat moment in het scherm staan (die zijn
 * corrigeerbaar). Een dag die al afgesloten was, wordt bijgewerkt.
 */
export function sluitDag({ datum, km, uren }) {
  const totalen = dagTotalen(datum);
  const velden = {
    datum,
    km: Number(km),
    uren: Number(uren),
    // Handmatig gecorrigeerde kilometers of uren blijven staan als de dag
    // later automatisch wordt bijgewerkt.
    kmHandmatig: Number(km) !== totalen.km,
    urenHandmatig: Number(uren) !== totalen.uren,
    aantalAfspraken: totalen.aantalAfspraken,
    omzetCent: totalen.omzetCent,
    productenCent: totalen.productenCent,
    cashCent: totalen.cashCent,
    bankCent: totalen.bankCent,
    openCent: totalen.openCent,
    afgeslotenOp: new Date().toISOString().slice(0, 16),
    bijgewerktOp: null,
  };

  const bestaand = getAfsluiting(datum);
  if (bestaand) {
    Object.assign(bestaand, velden);
    melden();
    return bestaand;
  }
  const afsluiting = { id: nieuwId(), ...velden };
  state.afsluitingen.push(afsluiting);
  melden();
  return afsluiting;
}

/**
 * Werkt de afsluiting van een of meer dagen bij nadat er iets aan de
 * afspraken van die dag is veranderd. Bedragen volgen altijd de afspraken;
 * kilometers en uren alleen als ze bij het afsluiten niet handmatig zijn
 * aangepast.
 */
function herberekenAfsluitingen(...datums) {
  new Set(datums.filter(Boolean)).forEach((datum) => {
    const afsluiting = getAfsluiting(datum);
    if (!afsluiting) return;
    const totalen = dagTotalen(datum);
    Object.assign(afsluiting, {
      aantalAfspraken: totalen.aantalAfspraken,
      omzetCent: totalen.omzetCent,
      productenCent: totalen.productenCent,
      cashCent: totalen.cashCent,
      bankCent: totalen.bankCent,
      openCent: totalen.openCent,
      bijgewerktOp: new Date().toISOString().slice(0, 16),
    });
    if (!afsluiting.kmHandmatig) afsluiting.km = totalen.km;
    if (!afsluiting.urenHandmatig) afsluiting.uren = totalen.uren;
  });
}

/** Maakt een afgesloten dag weer open, bijvoorbeeld om omzet te corrigeren. */
export function heropenDag(datum) {
  const index = state.afsluitingen.findIndex((a) => a.datum === datum);
  if (index === -1) return false;
  state.afsluitingen.splice(index, 1);
  melden();
  return true;
}

/*
 * Mock-gegevens. Deze app heeft (nog) geen backend: bij het laden van de
 * pagina wordt onderstaande startset in het geheugen gezet. Alles wat je
 * daarna invoert leeft alleen in dit browservenster en is na een refresh weer
 * weg. Datums worden relatief aan vandaag gemaakt, zodat de demo altijd
 * gevulde weken laat zien.
 */

import { naarISODatum } from "./format.js";

/** Snelkeuze voor een afspraak in de salon zelf. */
export const SALON = "In de salon";

/** ISO-datum van vandaag + n dagen. */
function dag(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return naarISODatum(d);
}

/** "2026-09-20T10:30" op n dagen van vandaag. */
function moment(n, tijd) {
  return `${dag(n)}T${tijd}`;
}

export function maakStartData() {
  const klanten = [
    { id: "k1", naam: "Anja de Vries", telefoon: "06 12 34 56 78", plaats: "Apeldoorn", afstandKm: 14, notitie: "Warm blond, geen kort model" },
    { id: "k2", naam: "Miriam Bakker", telefoon: "06 23 45 67 89", plaats: "Apeldoorn", afstandKm: 9, notitie: "" },
    { id: "k3", naam: "Sandra Hoekstra", telefoon: "06 34 56 78 90", plaats: "Beekbergen", afstandKm: 22, notitie: "Parkeren achter het huis" },
    { id: "k4", naam: "Jolanda Timmermans", telefoon: "06 45 67 89 01", plaats: "Ugchelen", afstandKm: 11, notitie: "" },
    { id: "k5", naam: "Karin Visser", telefoon: "06 56 78 90 12", plaats: "Apeldoorn", afstandKm: 7, notitie: "Belt vaak om te verzetten" },
    { id: "k6", naam: "Els Mulder", telefoon: "06 67 89 01 23", plaats: "Apeldoorn", afstandKm: 6, notitie: "" },
  ];

  const plaatsVan = (id) => klanten.find((klant) => klant.id === id).plaats;

  const afspraken = [
    // Afgelopen dag die al is afgesloten.
    { id: "a1", klantId: "k6", start: moment(-3, "11:00"), duurMin: 45, locatie: plaatsVan("k6"), behandeling: "Knippen", notitie: "Iets korter in de nek dan vorige keer.", omzet: { bedragCent: 3500, producten: [], betaald: true, methode: "cash" }, verplaatstVan: null },
    { id: "a2", klantId: "k5", start: moment(-3, "13:00"), duurMin: 60, locatie: plaatsVan("k5"), behandeling: "Knippen + föhnen", notitie: "Shampoo voor krullen verkocht, bevalt goed.", omzet: { bedragCent: 4000, producten: [{ id: "p1", omschrijving: "Shampoo krullen 250ml", bedragCent: 1495 }], betaald: true, methode: "cash" }, verplaatstVan: null },

    // Gisteren: nog niet afgesloten, en laat de drie omzet-toestanden zien.
    { id: "a3", klantId: "k1", start: moment(-1, "10:00"), duurMin: 60, locatie: plaatsVan("k1"), behandeling: "Knippen + föhnen", notitie: "Pony bijgeknipt, wil hem iets langer houden.", omzet: { bedragCent: 4500, producten: [], betaald: true, methode: "bank" }, verplaatstVan: null },
    { id: "a4", klantId: "k2", start: moment(-1, "13:30"), duurMin: 120, locatie: plaatsVan("k2"), behandeling: "Kleuren + knippen", notitie: "Kleur 7.1 met 6 vol oxidant, 35 min laten zitten.", omzet: { bedragCent: 8250, producten: [{ id: "p2", omschrijving: "Kleurbeschermende conditioner", bedragCent: 1850 }], betaald: false, methode: null }, verplaatstVan: null },
    { id: "a5", klantId: "k4", start: moment(-1, "16:00"), duurMin: 45, locatie: plaatsVan("k4"), behandeling: "Knippen", notitie: "", omzet: null, verplaatstVan: null },

    // Vandaag en verder.
    { id: "a6", klantId: "k5", start: moment(0, "09:30"), duurMin: 45, locatie: plaatsVan("k5"), behandeling: "Knippen", notitie: "", omzet: null, verplaatstVan: null },
    { id: "a7", klantId: "k3", start: moment(0, "14:00"), duurMin: 180, locatie: plaatsVan("k3"), behandeling: "Permanent", notitie: "", omzet: null, verplaatstVan: null },
    { id: "a8", klantId: "k4", start: moment(2, "10:00"), duurMin: 120, locatie: plaatsVan("k4"), behandeling: "Kleuren + knippen", notitie: "", omzet: null, verplaatstVan: moment(1, "10:00") },
    { id: "a9", klantId: "k1", start: moment(5, "11:00"), duurMin: 30, locatie: SALON, behandeling: "Föhnen", notitie: "", omzet: null, verplaatstVan: null },
    { id: "a10", klantId: "k6", start: moment(9, "15:30"), duurMin: 60, locatie: plaatsVan("k6"), behandeling: "Knippen + watergolf", notitie: "", omzet: null, verplaatstVan: null },
    { id: "a11", klantId: "k2", start: moment(16, "10:00"), duurMin: 90, locatie: plaatsVan("k2"), behandeling: "Kleuren", notitie: "", omzet: null, verplaatstVan: null },
  ];

  const stortingen = [
    { id: "s1", datum: dag(-10), bedragCent: 12000 },
    { id: "s2", datum: dag(-3), bedragCent: 7500 },
  ];

  const kosten = [
    { id: "ko1", datum: dag(-2), omschrijving: "Kleurmiddelen en shampoo", bedragCent: 8995, bon: { naam: "bon-groothandel.jpg", type: "image/jpeg", dataUrl: null } },
    { id: "ko2", datum: dag(-6), omschrijving: "Benzine", bedragCent: 6200, bon: null },
    { id: "ko3", datum: dag(-12), omschrijving: "Schaar laten slijpen", bedragCent: 2250, bon: null },
    { id: "ko4", datum: dag(-25), omschrijving: "Telefoonabonnement", bedragCent: 3500, bon: null },
  ];

  // Eén dag is al afgesloten; gisteren staat nog open, zodat de demo iets te
  // doen heeft op het tabblad Dagafsluiting.
  const afsluitingen = [
    {
      id: "af1",
      datum: dag(-3),
      km: 13,
      uren: 1.75,
      aantalAfspraken: 2,
      omzetCent: 8995,
      cashCent: 8995,
      bankCent: 0,
      openCent: 0,
      afgeslotenOp: `${dag(-3)}T17:10`,
    },
  ];

  return { klanten, afspraken, stortingen, kosten, afsluitingen };
}

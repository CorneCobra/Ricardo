/*
 * Mock-gegevens. Deze app heeft (nog) geen backend: bij het laden van de
 * pagina wordt onderstaande startset in het geheugen gezet. Alles wat je
 * daarna invoert leeft alleen in dit browservenster en is na een refresh weer
 * weg. Datums worden relatief aan vandaag gemaakt, zodat de demo altijd
 * gevulde weken laat zien.
 */

import { naarISODatum } from "./format.js";

/** Vaste locatie van de salon, als snelkeuze bij een afspraak. */
export const SALON = "Salon — Hoofdstraat 1, Apeldoorn";

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
    { id: "k1", naam: "Anja de Vries", telefoon: "06 12 34 56 78", adres: "Kerkstraat 12", plaats: "Apeldoorn", afstandKm: 14, notitie: "Warm blond, geen kort model" },
    { id: "k2", naam: "Miriam Bakker", telefoon: "06 23 45 67 89", adres: "Vondellaan 8", plaats: "Apeldoorn", afstandKm: 9, notitie: "" },
    { id: "k3", naam: "Sandra Hoekstra", telefoon: "06 34 56 78 90", adres: "Molenweg 45", plaats: "Beekbergen", afstandKm: 22, notitie: "Parkeren achter het huis" },
    { id: "k4", naam: "Jolanda Timmermans", telefoon: "06 45 67 89 01", adres: "Dorpsstraat 3", plaats: "Ugchelen", afstandKm: 11, notitie: "" },
    { id: "k5", naam: "Karin Visser", telefoon: "06 56 78 90 12", adres: "Prins Hendriklaan 27", plaats: "Apeldoorn", afstandKm: 7, notitie: "Belt vaak om te verzetten" },
    { id: "k6", naam: "Els Mulder", telefoon: "06 67 89 01 23", adres: "Loseweg 101", plaats: "Apeldoorn", afstandKm: 6, notitie: "" },
  ];

  const adresVan = (id) => {
    const k = klanten.find((klant) => klant.id === id);
    return `${k.adres}, ${k.plaats}`;
  };

  const afspraken = [
    // Afgelopen — laat de drie omzet-toestanden zien.
    { id: "a1", klantId: "k1", start: moment(-1, "10:00"), duurMin: 60, locatie: adresVan("k1"), behandeling: "Knippen + föhnen", omzet: { bedragCent: 4500, betaald: true, methode: "bank" }, verplaatstVan: null },
    { id: "a2", klantId: "k2", start: moment(-1, "13:30"), duurMin: 120, locatie: adresVan("k2"), behandeling: "Kleuren + knippen", omzet: { bedragCent: 8250, betaald: false, methode: null }, verplaatstVan: null },
    { id: "a3", klantId: "k6", start: moment(-3, "11:00"), duurMin: 45, locatie: adresVan("k6"), behandeling: "Knippen", omzet: null, verplaatstVan: null },

    // Vandaag en verder.
    { id: "a4", klantId: "k5", start: moment(0, "09:30"), duurMin: 45, locatie: adresVan("k5"), behandeling: "Knippen", omzet: null, verplaatstVan: null },
    { id: "a5", klantId: "k3", start: moment(0, "14:00"), duurMin: 180, locatie: adresVan("k3"), behandeling: "Permanent", omzet: null, verplaatstVan: null },
    { id: "a6", klantId: "k4", start: moment(2, "10:00"), duurMin: 120, locatie: adresVan("k4"), behandeling: "Kleuren + knippen", omzet: null, verplaatstVan: moment(1, "10:00") },
    { id: "a7", klantId: "k1", start: moment(5, "11:00"), duurMin: 30, locatie: SALON, behandeling: "Föhnen", omzet: null, verplaatstVan: null },
    { id: "a8", klantId: "k6", start: moment(9, "15:30"), duurMin: 60, locatie: adresVan("k6"), behandeling: "Knippen + watergolf", omzet: null, verplaatstVan: null },
    { id: "a9", klantId: "k2", start: moment(16, "10:00"), duurMin: 90, locatie: adresVan("k2"), behandeling: "Kleuren", omzet: null, verplaatstVan: null },
  ];

  const stortingen = [
    { id: "s1", datum: dag(-10), bedragCent: 12000 },
    { id: "s2", datum: dag(-3), bedragCent: 7500 },
  ];

  const dagen = [
    { id: "d1", datum: dag(-3), km: 6, uren: 2.5 },
    { id: "d2", datum: dag(-2), km: 18, uren: 6 },
    { id: "d3", datum: dag(-1), km: 23, uren: 5.5 },
  ];

  return { klanten, afspraken, stortingen, dagen };
}

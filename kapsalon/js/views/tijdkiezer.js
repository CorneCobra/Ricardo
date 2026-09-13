/*
 * Tijdkiezer: één component om een moment te prikken, met een weekstrip en
 * een kleine dagagenda erbij. Wordt gebruikt bij een nieuwe afspraak, bij een
 * vervolgafspraak en bij verplaatsen — overal zie je dus wat er al staat en
 * tik je een vrije plek aan in plaats van een datum te typen.
 */

import {
  DAG_EINDE,
  DAG_START,
  afsprakenOp,
  getKlant,
  overlapMet,
  tijdvakVan,
} from "../store.js";
import {
  alsDatum,
  dagLabel,
  naarISODatum,
  tijdVan,
  tijdVanMinuten,
  minutenVan,
  vandaagISO,
  veilig,
} from "../format.js";

/** Hoogte van één minuut in de kleine agenda. */
const PX_PER_MINUUT = 0.9;

const DAGLETTERS = ["ma", "di", "wo", "do", "vr", "za", "zo"];

/**
 * Tekent de tijdkiezer in container en geeft een kleine bediening terug.
 * onWijzig krijgt { datum, tijd } na elke keuze.
 */
export function maakTijdkiezer(container, { datum, tijd, duurMin, negeerId = null, onWijzig }) {
  const staat = { datum, tijd, duurMin, negeerId };

  /** Maandag van de week waarin datum valt. */
  function weekStart(iso) {
    const d = alsDatum(iso);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return d;
  }

  function verschuifWeek(stappen) {
    const d = alsDatum(staat.datum);
    d.setDate(d.getDate() + stappen * 7);
    staat.datum = naarISODatum(d);
    teken();
    onWijzig?.({ ...staat });
  }

  function kiesDatum(nieuweDatum) {
    staat.datum = nieuweDatum;
    teken();
    onWijzig?.({ ...staat });
  }

  function kiesTijd(nieuweTijd) {
    staat.tijd = nieuweTijd;
    teken();
    onWijzig?.({ ...staat });
  }

  function teken() {
    const start = weekStart(staat.datum);
    const dagen = [...Array(7)].map((_, i) => {
      const d = alsDatum(naarISODatum(start));
      d.setDate(d.getDate() + i);
      return naarISODatum(d);
    });

    const begin = minutenVan(staat.tijd);
    const einde = begin + (Number(staat.duurMin) || 60);
    const botsing = overlapMet({
      datum: staat.datum,
      tijd: staat.tijd,
      duurMin: staat.duurMin,
      negeerId: staat.negeerId,
    });

    const uren = [];
    for (let m = DAG_START; m <= DAG_EINDE; m += 60) {
      uren.push(
        `<div class="tk__uur" style="top:${(m - DAG_START) * PX_PER_MINUUT}px"><span>${tijdVanMinuten(m)}</span></div>`,
      );
    }

    container.innerHTML = `
      <div class="tk">
        <div class="tk__week">
          <button type="button" class="knop knop--stil knop--rond knop--klein" data-week="-1" aria-label="Vorige week">‹</button>
          <div class="tk__dagen" role="group" aria-label="Kies een dag">
            ${dagen.map((d, i) => dagKnop(d, i)).join("")}
          </div>
          <button type="button" class="knop knop--stil knop--rond knop--klein" data-week="1" aria-label="Volgende week">›</button>
        </div>

        <div class="tk__gekozen">
          <strong>${veilig(dagLabel(staat.datum))}</strong>
          <input type="time" step="300" value="${staat.tijd}" data-tijd aria-label="Tijd" />
        </div>

        <div class="tk__agenda" data-scroll style="--tk-hoogte:${(DAG_EINDE - DAG_START) * PX_PER_MINUUT}px">
          <div class="tk__vlak">
            <div class="tk__raster" data-raster>${uren.join("")}</div>
            ${afsprakenOp(staat.datum)
              .filter((a) => a.id !== staat.negeerId)
              .map(bestaandBlok)
              .join("")}
            <div class="tk__nieuw ${botsing.length ? "tk__nieuw--botst" : ""}"
                 style="top:${(begin - DAG_START) * PX_PER_MINUUT}px;height:${Math.max(24, (einde - begin) * PX_PER_MINUUT)}px">
              ${tijdVanMinuten(begin)} – ${tijdVanMinuten(einde)}
            </div>
          </div>
        </div>

        <p class="tk__melding ${botsing.length ? "tk__melding--botst" : ""}">
          ${
            botsing.length
              ? `Overlapt met ${veilig(botsing.map((a) => getKlant(a.klantId)?.naam || "een afspraak").join(" en "))}.`
              : "Tik in de agenda om een tijd te kiezen."
          }
        </p>
      </div>
    `;

    container.querySelectorAll("[data-week]").forEach((knop) =>
      knop.addEventListener("click", () => verschuifWeek(Number(knop.dataset.week))),
    );
    container.querySelectorAll("[data-datum]").forEach((knop) =>
      knop.addEventListener("click", () => kiesDatum(knop.dataset.datum)),
    );
    container.querySelector("[data-tijd]").addEventListener("change", (event) => {
      if (event.target.value) kiesTijd(event.target.value);
    });

    // Tikken in de agenda prikt het dichtstbijzijnde kwartier.
    container.querySelector("[data-raster]").addEventListener("click", (event) => {
      const vlak = event.currentTarget.getBoundingClientRect();
      const minuten = DAG_START + (event.clientY - vlak.top) / PX_PER_MINUUT;
      const afgerond = Math.min(
        DAG_EINDE - 15,
        Math.max(DAG_START, Math.round(minuten / 15) * 15),
      );
      kiesTijd(tijdVanMinuten(afgerond));
    });

    // Zorg dat het gekozen moment in beeld staat.
    const scroll = container.querySelector("[data-scroll]");
    scroll.scrollTop = Math.max(0, (begin - DAG_START) * PX_PER_MINUUT - 70);
  }

  function dagKnop(datum, index) {
    const aantal = afsprakenOp(datum).filter((a) => a.id !== staat.negeerId).length;
    const actief = datum === staat.datum;
    return `
      <button type="button" class="tk__dag ${actief ? "tk__dag--actief" : ""} ${datum === vandaagISO() ? "tk__dag--vandaag" : ""}"
              data-datum="${datum}" aria-pressed="${actief}" aria-label="${veilig(dagLabel(datum))}">
        <span>${DAGLETTERS[index]}</span>
        <strong>${Number(datum.slice(8))}</strong>
        <i class="tk__punten" aria-hidden="true">${"•".repeat(Math.min(aantal, 3))}</i>
      </button>
    `;
  }

  function bestaandBlok(afspraak) {
    const vak = tijdvakVan(afspraak);
    const hoogte = Math.max(18, (vak.einde - vak.begin) * PX_PER_MINUUT);
    const klant = getKlant(afspraak.klantId);
    return `
      <div class="tk__bezet" style="top:${(vak.begin - DAG_START) * PX_PER_MINUUT}px;height:${hoogte}px">
        ${tijdVan(afspraak.start)} ${veilig(klant ? klant.naam : "bezet")}
      </div>
    `;
  }

  teken();

  return {
    get datum() {
      return staat.datum;
    },
    get tijd() {
      return staat.tijd;
    },
    /** Van buitenaf een ander moment of een andere duur zetten. */
    zet(velden) {
      Object.assign(staat, velden);
      teken();
    },
  };
}

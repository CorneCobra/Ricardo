/*
 * Tab "Km & uren": per dag kilometers en uren vastleggen. De kilometers
 * worden voorgesteld op basis van de vaste afstand per klant bij de
 * afspraken van die dag; je kunt ze altijd overschrijven.
 */

import {
  aantalAfsprakenOp,
  getDag,
  getDagen,
  verwijderDag,
  voorgesteldeKm,
  zetDag,
} from "../store.js";
import { dagKort, getal, maandLabel, vandaagISO, veilig } from "../format.js";
import { melding } from "../ui.js";

// Onthoudt de laatst gekozen datum, zodat die na het opslaan niet terugspringt
// naar vandaag.
let laatsteDatum = null;

export function render(root) {
  const dagen = getDagen();
  const gekozenDatum = laatsteDatum || vandaagISO();
  const dezeMaand = vandaagISO().slice(0, 7);
  const vanDezeMaand = dagen.filter((d) => d.datum.startsWith(dezeMaand));
  const totaalKm = vanDezeMaand.reduce((som, d) => som + (Number(d.km) || 0), 0);
  const totaalUren = vanDezeMaand.reduce((som, d) => som + (Number(d.uren) || 0), 0);

  root.innerHTML = `
    <div class="kop"><h2>Kilometers &amp; uren</h2></div>

    <form class="paneel" id="form-dag" novalidate>
      <div class="veld">
        <label for="dag-datum">Datum</label>
        <input id="dag-datum" name="datum" type="date" value="${gekozenDatum}" required />
      </div>
      <div class="veld veld--duo">
        <div>
          <label for="dag-km">Kilometers</label>
          <input id="dag-km" name="km" type="number" inputmode="decimal" min="0" step="0.1" required />
        </div>
        <div>
          <label for="dag-uren">Uren</label>
          <input id="dag-uren" name="uren" type="number" inputmode="decimal" min="0" step="0.25" placeholder="3,5" required />
        </div>
      </div>
      <p class="hint" data-voorstel></p>
      <p class="dlg__fout" data-fout hidden></p>
      <button type="submit" class="knop knop--breed">Dag opslaan</button>
    </form>

    <div class="totaal">
      <span>Totaal ${veilig(maandLabel(vandaagISO()))}</span>
      <strong>${getal(totaalKm)} km · ${getal(totaalUren)} uur</strong>
    </div>

    ${
      dagen.length === 0
        ? `<p class="leeg">Nog niets geregistreerd.</p>`
        : `<ul class="lijst">${dagen.map(regel).join("")}</ul>`
    }
  `;

  const form = root.querySelector("#form-dag");
  const fout = form.querySelector("[data-fout]");
  const voorstel = form.querySelector("[data-voorstel]");

  /** Vult km/uren op basis van een bestaande registratie of een voorstel. */
  function vulVoor(datum) {
    const bestaand = getDag(datum);
    if (bestaand) {
      form.km.value = bestaand.km;
      form.uren.value = bestaand.uren;
      voorstel.textContent =
        "Deze dag is al geregistreerd — opslaan werkt de bestaande registratie bij.";
      return;
    }
    const km = voorgesteldeKm(datum);
    const aantal = aantalAfsprakenOp(datum);
    form.km.value = km || "";
    form.uren.value = "";
    voorstel.textContent = aantal
      ? `Voorstel op basis van ${aantal} ${aantal === 1 ? "afspraak" : "afspraken"} op deze dag. Je kunt het aanpassen.`
      : "Geen afspraken op deze dag — vul de kilometers zelf in.";
  }

  vulVoor(form.datum.value);
  form.datum.addEventListener("change", () => {
    laatsteDatum = form.datum.value;
    vulVoor(form.datum.value);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.datum.value) {
      fout.textContent = "Kies een datum.";
      fout.hidden = false;
      return;
    }
    if (form.km.value === "" || form.uren.value === "") {
      fout.textContent = "Vul zowel kilometers als uren in.";
      fout.hidden = false;
      return;
    }
    zetDag({
      datum: form.datum.value,
      km: Number(form.km.value),
      uren: Number(form.uren.value),
    });
    melding("Dag opgeslagen");
  });

  root.querySelectorAll("[data-verwijder-dag]").forEach((knop) =>
    knop.addEventListener("click", () => {
      verwijderDag(knop.dataset.verwijderDag);
      melding("Registratie verwijderd");
    }),
  );
}

function regel(dag) {
  return `
    <li class="kaart kaart--regel">
      <div>
        <strong>${veilig(dagKort(dag.datum))}</strong>
        <span class="kaart__regel kaart__regel--stil">${getal(dag.km)} km · ${getal(dag.uren)} uur</span>
      </div>
      <button type="button" class="knop knop--kaal knop--klein" data-verwijder-dag="${dag.id}">Verwijderen</button>
    </li>
  `;
}

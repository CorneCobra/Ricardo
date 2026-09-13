/*
 * Tab "Storting": omzet die naar de bank is gebracht. Alleen een bedrag en
 * een datum — verder niets, zoals afgesproken.
 */

import { getStortingen, verwijderStorting, voegStortingToe } from "../store.js";
import { dagKort, euro, maandLabel, naarCent, vandaagISO, veilig } from "../format.js";
import { melding } from "../ui.js";

// Onthoudt de laatst gekozen datum binnen deze sessie.
let laatsteDatum = null;

export function render(root) {
  const stortingen = getStortingen();
  const gekozenDatum = laatsteDatum || vandaagISO();
  const dezeMaand = vandaagISO().slice(0, 7);
  const totaalMaand = stortingen
    .filter((s) => s.datum.startsWith(dezeMaand))
    .reduce((som, s) => som + s.bedragCent, 0);

  root.innerHTML = `
    <div class="kop"><h2>Omzetstorting</h2></div>

    <form class="paneel" id="form-storting" novalidate>
      <div class="veld veld--duo">
        <div>
          <label for="storting-bedrag">Bedrag</label>
          <div class="veld__valuta">
            <span aria-hidden="true">€</span>
            <input id="storting-bedrag" name="bedrag" type="text" inputmode="decimal" placeholder="120,00" required />
          </div>
        </div>
        <div>
          <label for="storting-datum">Datum</label>
          <input id="storting-datum" name="datum" type="date" value="${gekozenDatum}" required />
        </div>
      </div>
      <p class="dlg__fout" data-fout hidden></p>
      <button type="submit" class="knop knop--breed">Storting toevoegen</button>
    </form>

    <div class="totaal">
      <span>Gestort in ${veilig(maandLabel(vandaagISO()))}</span>
      <strong>${euro(totaalMaand)}</strong>
    </div>

    ${
      stortingen.length === 0
        ? `<p class="leeg">Nog geen stortingen geregistreerd.</p>`
        : `<ul class="lijst">${stortingen.map(regel).join("")}</ul>`
    }
  `;

  const form = root.querySelector("#form-storting");
  const fout = form.querySelector("[data-fout]");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const bedragCent = naarCent(form.bedrag.value);
    if (bedragCent === null || bedragCent <= 0) {
      fout.textContent = "Vul een bedrag in, bijvoorbeeld 120,00.";
      fout.hidden = false;
      return;
    }
    if (!form.datum.value) {
      fout.textContent = "Kies een datum.";
      fout.hidden = false;
      return;
    }
    laatsteDatum = form.datum.value;
    voegStortingToe({ datum: form.datum.value, bedragCent });
    melding("Storting toegevoegd");
  });

  root.querySelectorAll("[data-verwijder-storting]").forEach((knop) =>
    knop.addEventListener("click", () => {
      verwijderStorting(knop.dataset.verwijderStorting);
      melding("Storting verwijderd");
    }),
  );
}

function regel(storting) {
  return `
    <li class="kaart kaart--regel">
      <div>
        <strong>${euro(storting.bedragCent)}</strong>
        <span class="kaart__regel kaart__regel--stil">${veilig(dagKort(storting.datum))}</span>
      </div>
      <button type="button" class="knop knop--kaal knop--klein" data-verwijder-storting="${storting.id}">Verwijderen</button>
    </li>
  `;
}

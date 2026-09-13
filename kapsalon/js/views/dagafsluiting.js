/*
 * Tab "Afsluiten": de dagafsluiting. Je kiest een dag en ziet wat die dag
 * heeft opgeleverd — omzet gesplitst naar cash, bank en nog openstaand — plus
 * de kilometers en gewerkte uren, berekend uit de afspraken van die dag.
 * Kilometers en uren zijn corrigeerbaar voordat je de dag vastzet.
 */

import {
  afsprakenOp,
  dagTotalen,
  getAfsluiting,
  getAfsluitingen,
  getKlant,
  heropenDag,
  sluitDag,
} from "../store.js";
import {
  dagKort,
  dagLabel,
  euro,
  getal,
  naarISODatum,
  tijdVan,
  tijdvak,
  vandaagISO,
  veilig,
} from "../format.js";
import { melding } from "../ui.js";
import { koppelKaartknoppen, omzetBadge } from "./afspraken.js";

// De gekozen dag blijft staan zolang de app open is.
let datum = vandaagISO();

export function render(root) {
  const totalen = dagTotalen(datum);
  const afsluiting = getAfsluiting(datum);
  const afspraken = afsprakenOp(datum);
  const eerdere = getAfsluitingen().filter((a) => a.datum !== datum);

  root.innerHTML = `
    <div class="kop"><h2>Dagafsluiting</h2></div>

    <div class="dagkiezer">
      <button type="button" class="knop knop--stil knop--rond" data-dag="-1" aria-label="Vorige dag">‹</button>
      <div class="dagkiezer__midden">
        <strong>${veilig(dagLabel(datum))}</strong>
        <input type="date" value="${datum}" data-dagdatum aria-label="Kies een dag" />
      </div>
      <button type="button" class="knop knop--stil knop--rond" data-dag="1" aria-label="Volgende dag">›</button>
    </div>

    ${
      afsluiting
        ? `<p class="badges"><span class="badge badge--ok">Afgesloten · vastgelegd ${veilig(dagKort(afsluiting.afgeslotenOp))} ${tijdVan(afsluiting.afgeslotenOp)}</span></p>`
        : ""
    }

    <div class="paneel paneel--totalen">
      <div class="cijfer cijfer--groot">
        <span>Omzet</span>
        <strong>${euro(totalen.omzetCent)}</strong>
      </div>
      <div class="cijfers">
        <div class="cijfer"><span>Cash</span><strong>${euro(totalen.cashCent)}</strong></div>
        <div class="cijfer"><span>Bank</span><strong>${euro(totalen.bankCent)}</strong></div>
        <div class="cijfer ${totalen.openCent ? "cijfer--open" : ""}"><span>Openstaand</span><strong>${euro(totalen.openCent)}</strong></div>
      </div>
      <div class="cijfers">
        <div class="cijfer"><span>Afspraken</span><strong>${totalen.aantalAfspraken}</strong></div>
        <div class="cijfer"><span>Kilometers</span><strong>${getal(totalen.km)} km</strong></div>
        <div class="cijfer"><span>Gewerkt</span><strong>${getal(totalen.uren, 2)} uur</strong></div>
      </div>
      <p class="hint">
        Kilometers uit de vaste afstand van de klanten van deze dag (dezelfde
        klant telt één rit); uren uit de duur van de afspraken.
      </p>
    </div>

    ${
      totalen.zonderOmzet
        ? `<p class="waarschuwing">Nog ${totalen.zonderOmzet} ${totalen.zonderOmzet === 1 ? "afspraak" : "afspraken"} zonder omzet. Vul die eerst in, dan klopt de afsluiting.</p>`
        : ""
    }

    <form class="paneel" id="form-afsluiten" novalidate>
      <div class="veld veld--duo">
        <div>
          <label for="afsluit-km">Kilometers</label>
          <input id="afsluit-km" name="km" type="number" inputmode="decimal" min="0" step="0.1"
            value="${afsluiting ? afsluiting.km : totalen.km}" />
        </div>
        <div>
          <label for="afsluit-uren">Uren</label>
          <input id="afsluit-uren" name="uren" type="number" inputmode="decimal" min="0" step="0.25"
            value="${afsluiting ? afsluiting.uren : totalen.uren}" />
        </div>
      </div>
      <p class="hint">Berekend uit deze dag — pas aan als je extra hebt gereden of gewerkt.</p>
      <p class="dlg__fout" data-fout hidden></p>
      <div class="veld__rij">
        <button type="submit" class="knop knop--breed">
          ${afsluiting ? "Afsluiting bijwerken" : "Dag afsluiten"}
        </button>
        ${afsluiting ? `<button type="button" class="knop knop--stil" data-heropen>Heropenen</button>` : ""}
      </div>
    </form>

    <h3 class="groep__kop">Afspraken op deze dag</h3>
    ${
      afspraken.length === 0
        ? `<p class="leeg">Geen afspraken op deze dag.</p>`
        : `<ul class="lijst">${afspraken.map(regel).join("")}</ul>`
    }

    ${
      eerdere.length
        ? `<h3 class="groep__kop">Eerder afgesloten</h3>
           <ul class="lijst">${eerdere.slice(0, 10).map(eerderRegel).join("")}</ul>`
        : ""
    }
  `;

  root.querySelectorAll("[data-dag]").forEach((knop) =>
    knop.addEventListener("click", () => {
      const d = new Date(`${datum}T12:00`);
      d.setDate(d.getDate() + Number(knop.dataset.dag));
      datum = naarISODatum(d);
      render(root);
    }),
  );

  root.querySelector("[data-dagdatum]").addEventListener("change", (event) => {
    if (!event.target.value) return;
    datum = event.target.value;
    render(root);
  });

  const form = root.querySelector("#form-afsluiten");
  const fout = form.querySelector("[data-fout]");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (form.km.value === "" || form.uren.value === "") {
      fout.textContent = "Vul kilometers en uren in.";
      fout.hidden = false;
      return;
    }
    sluitDag({ datum, km: Number(form.km.value), uren: Number(form.uren.value) });
    melding(afsluiting ? "Afsluiting bijgewerkt" : "Dag afgesloten");
  });

  root.querySelectorAll("[data-bekijk]").forEach((knop) =>
    knop.addEventListener("click", () => {
      datum = knop.dataset.bekijk;
      render(root);
    }),
  );

  root.querySelector("[data-heropen]")?.addEventListener("click", () => {
    heropenDag(datum);
    melding("Dag weer open");
  });

  koppelKaartknoppen(root);
}

/** Compacte regel per afspraak, met de knoppen uit het afsprakenscherm. */
function regel(afspraak) {
  const klant = getKlant(afspraak.klantId);
  return `
    <li class="kaart">
      <div class="kaart__kop">
        <div>
          <h3>${veilig(klant ? klant.naam : "Onbekende klant")}</h3>
          <p class="kaart__behandeling">${veilig([tijdvak(afspraak.start, afspraak.duurMin), afspraak.behandeling].filter(Boolean).join(" · "))}</p>
        </div>
      </div>
      <p class="badges">${omzetBadge(afspraak.omzet)}</p>
      <div class="kaart__acties">
        <button type="button" class="knop knop--klein" data-omzet="${afspraak.id}">
          ${afspraak.omzet ? "Omzet aanpassen" : "Omzet"}
        </button>
      </div>
    </li>
  `;
}

function eerderRegel(afsluiting) {
  return `
    <li class="kaart kaart--regel">
      <div>
        <strong>${veilig(dagKort(afsluiting.datum))}</strong>
        <span class="kaart__regel kaart__regel--stil">
          ${euro(afsluiting.omzetCent)} · ${getal(afsluiting.km)} km · ${getal(afsluiting.uren, 2)} uur
        </span>
      </div>
      <button type="button" class="knop knop--stil knop--klein" data-bekijk="${afsluiting.datum}">Bekijk</button>
    </li>
  `;
}

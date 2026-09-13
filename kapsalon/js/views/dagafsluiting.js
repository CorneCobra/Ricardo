/*
 * Tab "Afsluiten": een korte lijst van de dagen die nog afgesloten moeten
 * worden. Tik op een dag en je krijgt de cijfers van die dag — omzet
 * gesplitst naar cash, bank en openstaand, plus kilometers en uren die uit de
 * afspraken berekend zijn — en sluit hem daar af.
 */

import {
  afsprakenOp,
  dagTotalen,
  getAfsluiting,
  getAfsluitingen,
  getKlant,
  heropenDag,
  openDagen,
  sluitDag,
} from "../store.js";
import {
  dagKort,
  dagLabel,
  euro,
  getal,
  tijdVan,
  tijdvak,
  veilig,
} from "../format.js";
import { melding, openDialoog } from "../ui.js";
import { koppelAfspraakKlik, omzetRegel } from "./afspraken.js";

// De dag die op dit moment in de dialoog staat.
let dialoogDatum = null;

export function render(root) {
  const open = openDagen();
  const afgesloten = getAfsluitingen();

  root.innerHTML = `
    <div class="kop"><h2>Afsluiten</h2></div>

    ${
      open.length
        ? `<ul class="lijst lijst--dicht">${open.map(openRegel).join("")}</ul>`
        : `<p class="leeg">Alles is afgesloten. Netjes.</p>`
    }

    ${
      afgesloten.length
        ? `<h3 class="groep__kop">Afgesloten</h3>
           <ul class="lijst lijst--dicht">${afgesloten.slice(0, 14).map(afgeslotenRegel).join("")}</ul>`
        : ""
    }
  `;

  root.querySelectorAll("[data-dagrij]").forEach((rij) =>
    rij.addEventListener("click", () => openDagDialoog(rij.dataset.dagrij)),
  );
  root.querySelectorAll("[data-dagrij]").forEach((rij) =>
    rij.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openDagDialoog(rij.dataset.dagrij);
    }),
  );

  // Staat de dagdialoog open, dan moet die meebewegen met wijzigingen.
  const dlg = document.getElementById("dlg-dag");
  if (dlg.open && dialoogDatum) vulDagDialoog(dialoogDatum);
}

/** Compacte regel voor een dag die nog open staat. */
function openRegel(totalen) {
  return `
    <li class="rij rij--klikbaar" data-dagrij="${totalen.datum}" tabindex="0" role="button"
        aria-label="${veilig(dagLabel(totalen.datum))} afsluiten">
      <div class="rij__kop">
        <strong>${veilig(dagLabel(totalen.datum))}</strong>
        <span class="rij__bedrag">${euro(totalen.omzetCent)}</span>
      </div>
      <div class="rij__meta">
        <span>${totalen.aantalAfspraken}× · ${getal(totalen.km)} km · ${getal(totalen.uren, 2)} uur</span>
        ${totalen.zonderOmzet ? `<span class="rij__let-op">${totalen.zonderOmzet} zonder omzet</span>` : ""}
      </div>
    </li>
  `;
}

/** Compacte regel voor een dag die al is afgesloten. */
function afgeslotenRegel(afsluiting) {
  return `
    <li class="rij rij--klikbaar rij--klaar" data-dagrij="${afsluiting.datum}" tabindex="0" role="button"
        aria-label="${veilig(dagKort(afsluiting.datum))} bekijken">
      <div class="rij__kop">
        <strong>${veilig(dagKort(afsluiting.datum))}</strong>
        <span class="rij__bedrag">${euro(afsluiting.omzetCent)}</span>
      </div>
      <div class="rij__meta">
        <span>${getal(afsluiting.km)} km · ${getal(afsluiting.uren, 2)} uur</span>
      </div>
    </li>
  `;
}

/* --------------------------------------------------------- de dagdialoog */

function openDagDialoog(datum) {
  dialoogDatum = datum;
  const dlg = document.getElementById("dlg-dag");
  const form = document.getElementById("form-dag");

  vulDagDialoog(datum);

  form.onsubmit = (event) => {
    event.preventDefault();
    const fout = form.querySelector("[data-fout]");
    if (form.km.value === "" || form.uren.value === "") {
      fout.textContent = "Vul kilometers en uren in.";
      fout.hidden = false;
      return;
    }
    const bestond = Boolean(getAfsluiting(datum));
    sluitDag({ datum, km: Number(form.km.value), uren: Number(form.uren.value) });
    dlg.close();
    melding(bestond ? "Afsluiting bijgewerkt" : "Dag afgesloten");
  };

  document.getElementById("dag-heropen").onclick = () => {
    heropenDag(datum);
    dlg.close();
    melding("Dag weer open");
  };

  openDialoog(dlg);
}

/** Tekent de inhoud van de dagdialoog; ook na een wijziging in de store. */
function vulDagDialoog(datum) {
  const form = document.getElementById("form-dag");
  const totalen = dagTotalen(datum);
  const afsluiting = getAfsluiting(datum);
  const afspraken = afsprakenOp(datum);

  document.getElementById("dag-titel").textContent = dagLabel(datum);
  document.getElementById("dag-context").textContent = afsluiting
    ? `Afgesloten · vastgelegd ${dagKort(afsluiting.afgeslotenOp)} ${tijdVan(afsluiting.afgeslotenOp)}` +
      (afsluiting.bijgewerktOp
        ? ` · bijgewerkt ${dagKort(afsluiting.bijgewerktOp)} ${tijdVan(afsluiting.bijgewerktOp)}`
        : "")
    : `${totalen.aantalAfspraken} ${totalen.aantalAfspraken === 1 ? "afspraak" : "afspraken"} op deze dag`;

  document.getElementById("dag-inhoud").innerHTML = `
    <div class="paneel paneel--totalen paneel--plat">
      <div class="cijfers cijfers--duo">
        <div class="cijfer cijfer--groot"><span>Omzet</span><strong>${euro(totalen.omzetCent)}</strong></div>
        <div class="cijfer ${totalen.openCent ? "cijfer--open" : ""}">
          <span>Te ontvangen</span><strong>${euro(totalen.openCent)}</strong>
        </div>
      </div>
      <details class="sectie sectie--plat">
        <summary>Details</summary>
        <div class="cijfers">
          <div class="cijfer"><span>Cash</span><strong>${euro(totalen.cashCent)}</strong></div>
          <div class="cijfer"><span>Bank</span><strong>${euro(totalen.bankCent)}</strong></div>
          <div class="cijfer"><span>Producten</span><strong>${euro(totalen.productenCent)}</strong></div>
        </div>
      </details>
    </div>

    ${
      totalen.zonderOmzet
        ? `<p class="waarschuwing">${totalen.zonderOmzet} ${totalen.zonderOmzet === 1 ? "afspraak" : "afspraken"} zonder omzet.</p>`
        : ""
    }

    ${
      afspraken.length
        ? `<ul class="lijst lijst--dicht">${afspraken.map(afspraakRegel).join("")}</ul>`
        : `<p class="leeg">Geen afspraken op deze dag.</p>`
    }
  `;

  form.km.value = afsluiting ? afsluiting.km : totalen.km;
  form.uren.value = afsluiting ? afsluiting.uren : totalen.uren;
  form.querySelector("[data-fout]").hidden = true;

  document.getElementById("dag-opslaan").textContent = afsluiting
    ? "Afsluiting bijwerken"
    : "Dag afsluiten";
  document.getElementById("dag-heropen").hidden = !afsluiting;

  koppelAfspraakKlik(document.getElementById("dag-inhoud"));
}

function afspraakRegel(afspraak) {
  const klant = getKlant(afspraak.klantId);
  return `
    <li class="rij rij--klikbaar" data-afspraak="${afspraak.id}" tabindex="0" role="button"
        aria-label="Afspraak met ${veilig(klant ? klant.naam : "onbekende klant")} openen">
      <div class="rij__kop">
        <strong>${veilig(klant ? klant.naam : "Onbekende klant")}</strong>
        <span class="rij__bedrag">${tijdvak(afspraak.start, afspraak.duurMin)}</span>
      </div>
      <div class="rij__meta">${omzetRegel(afspraak.omzet)}</div>
    </li>
  `;
}

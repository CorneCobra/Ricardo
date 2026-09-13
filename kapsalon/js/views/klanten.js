/*
 * Tab "Klanten": het lijstje dat op de achtergrond wordt bijgehouden, zodat
 * een nieuwe afspraak alleen nog een keuze uit deze lijst is. De afstand per
 * klant voedt het kilometervoorstel in de tab "Km & uren".
 */

import { getKlanten, getKlant, voegKlantToe, wijzigKlant } from "../store.js";
import { getal, veilig } from "../format.js";
import { melding, openDialoog, toonFout } from "../ui.js";
import { whatsappKnop } from "./afspraken.js";

export function render(root) {
  const klanten = getKlanten();

  root.innerHTML = `
    <div class="kop">
      <h2>Klanten</h2>
      <button type="button" class="knop" data-nieuwe-klant>+ Nieuwe klant</button>
    </div>
    ${
      klanten.length === 0
        ? `<p class="leeg">Nog geen klanten. Voeg je eerste klant toe.</p>`
        : `<ul class="lijst">${klanten.map(kaart).join("")}</ul>`
    }
  `;

  root.querySelector("[data-nieuwe-klant]")?.addEventListener("click", () => {
    openKlantDialoog();
  });

  root.querySelectorAll("[data-bewerk-klant]").forEach((knop) => {
    knop.addEventListener("click", () => {
      openKlantDialoog({ klantId: knop.dataset.bewerkKlant });
    });
  });
}

function kaart(klant) {
  return `
    <li class="kaart">
      <div class="kaart__kop">
        <h3>${veilig(klant.naam)}</h3>
        <button type="button" class="knop knop--stil knop--klein" data-bewerk-klant="${klant.id}">Bewerken</button>
      </div>
      ${klant.telefoon ? whatsappKnop(klant) : ""}
      ${klant.plaats ? `<p class="kaart__regel"><span aria-hidden="true">📍</span> ${veilig(klant.plaats)}</p>` : ""}
      <p class="kaart__regel kaart__regel--stil">
        <span aria-hidden="true">🚗</span> ${getal(klant.afstandKm)} km heen en terug
      </p>
      ${klant.notitie ? `<p class="kaart__notitie">${veilig(klant.notitie)}</p>` : ""}
    </li>
  `;
}

/**
 * Dialoog voor een nieuwe klant of het bewerken van een bestaande.
 * onOpgeslagen krijgt de klant mee, zodat de afsprakendialoog een zojuist
 * toegevoegde klant meteen kan selecteren.
 */
export function openKlantDialoog({ klantId = null, onOpgeslagen } = {}) {
  const dlg = document.getElementById("dlg-klant");
  const form = document.getElementById("form-klant");
  const klant = klantId ? getKlant(klantId) : null;

  document.getElementById("dlg-klant-titel").textContent = klant
    ? "Klant bewerken"
    : "Nieuwe klant";
  form.naam.value = klant?.naam || "";
  form.telefoon.value = klant?.telefoon || "";
  form.plaats.value = klant?.plaats || "";
  form.afstandKm.value = klant ? klant.afstandKm : "";
  form.notitie.value = klant?.notitie || "";

  form.onsubmit = (event) => {
    event.preventDefault();
    const velden = {
      naam: form.naam.value.trim(),
      telefoon: form.telefoon.value.trim(),
      plaats: form.plaats.value.trim(),
      afstandKm: Number(form.afstandKm.value) || 0,
      notitie: form.notitie.value.trim(),
    };
    if (!velden.naam) return toonFout(dlg, "Vul een naam in.");
    if (!velden.telefoon) return toonFout(dlg, "Vul een telefoonnummer in.");

    const bewaard = klant
      ? wijzigKlant(klant.id, velden)
      : voegKlantToe(velden);
    dlg.close();
    melding(klant ? "Klant bijgewerkt" : `${bewaard.naam} toegevoegd`);
    onOpgeslagen?.(bewaard);
  };

  openDialoog(dlg);
  form.naam.focus();
}

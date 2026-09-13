/*
 * Tab "Afspraken": het startscherm. Toont de komende afspraken per dag, met
 * per afspraak wie, waar, hoe laat, het telefoonnummer en de omzetstatus.
 * Vanaf hier registreer je omzet en verplaats je een afspraak.
 */

import {
  adresVanKlant,
  getAfgelopenAfspraken,
  getAfspraak,
  getKlant,
  getKlanten,
  getKomendeAfspraken,
  verplaatsAfspraak,
  verwijderAfspraak,
  voegAfspraakToe,
  zetOmzet,
} from "../store.js";
import { SALON } from "../data.js";
import {
  dagLabel,
  datumVan,
  duurLabel,
  euro,
  naarCent,
  tijdVan,
  telHref,
  vandaagISO,
  veilig,
} from "../format.js";
import { melding, openDialoog, toonFout } from "../ui.js";
import { openKlantDialoog } from "./klanten.js";

// Blijft bewaard zolang de app open staat, zodat het filter niet terugspringt
// bij elke wijziging.
let toonAfgelopen = false;

export function render(root) {
  const komend = getKomendeAfspraken();
  const afgelopen = toonAfgelopen ? getAfgelopenAfspraken() : [];

  root.innerHTML = `
    <div class="kop">
      <h2>Afspraken</h2>
      <button type="button" class="knop" data-nieuwe-afspraak>+ Nieuwe afspraak</button>
    </div>

    <label class="schakel schakel--filter">
      <input type="checkbox" data-filter ${toonAfgelopen ? "checked" : ""} />
      <span>Toon ook afgelopen afspraken</span>
    </label>

    ${
      toonAfgelopen
        ? afgelopen.length
          ? `<h3 class="groep__kop groep__kop--terug">Afgelopen</h3>${groepen(afgelopen)}`
          : `<p class="leeg">Geen afgelopen afspraken.</p>`
        : ""
    }

    ${
      komend.length === 0
        ? `<p class="leeg">Geen komende afspraken. Plan er een in met <strong>+ Nieuwe afspraak</strong>.</p>`
        : groepen(komend)
    }
  `;

  root.querySelector("[data-nieuwe-afspraak]")?.addEventListener("click", () => {
    openAfspraakDialoog();
  });

  root.querySelector("[data-filter]")?.addEventListener("change", (event) => {
    toonAfgelopen = event.target.checked;
    render(root);
  });

  root.querySelectorAll("[data-omzet]").forEach((knop) =>
    knop.addEventListener("click", () => openOmzetDialoog(knop.dataset.omzet)),
  );
  root.querySelectorAll("[data-verplaats]").forEach((knop) =>
    knop.addEventListener("click", () => openVerplaatsDialoog(knop.dataset.verplaats)),
  );
  root.querySelectorAll("[data-verwijder]").forEach((knop) =>
    knop.addEventListener("click", () => {
      const afspraak = getAfspraak(knop.dataset.verwijder);
      const klant = getKlant(afspraak?.klantId);
      if (!afspraak) return;
      const naam = klant ? klant.naam : "deze klant";
      if (confirm(`Afspraak met ${naam} verwijderen?`)) {
        verwijderAfspraak(afspraak.id);
        melding("Afspraak verwijderd");
      }
    }),
  );
}

/** Afspraken gegroepeerd onder een dagkop, in de volgorde die binnenkomt. */
function groepen(afspraken) {
  const perDag = new Map();
  afspraken.forEach((afspraak) => {
    const datum = datumVan(afspraak.start);
    if (!perDag.has(datum)) perDag.set(datum, []);
    perDag.get(datum).push(afspraak);
  });

  return [...perDag.entries()]
    .map(
      ([datum, items]) => `
        <section class="groep">
          <h3 class="groep__kop">${veilig(dagLabel(datum))}</h3>
          <ul class="lijst">${items.map(kaart).join("")}</ul>
        </section>
      `,
    )
    .join("");
}

function kaart(afspraak) {
  const klant = getKlant(afspraak.klantId);
  const naam = klant ? klant.naam : "Onbekende klant";
  const isVerleden = datumVan(afspraak.start) < vandaagISO();

  return `
    <li class="kaart kaart--afspraak ${isVerleden ? "kaart--verleden" : ""}">
      <div class="kaart__kop">
        <div>
          <h3>${veilig(naam)}</h3>
          ${afspraak.behandeling ? `<p class="kaart__behandeling">${veilig(afspraak.behandeling)}</p>` : ""}
        </div>
        <span class="tijd">
          <strong>${tijdVan(afspraak.start)}</strong>
          <small>${veilig(duurLabel(afspraak.duurMin))}</small>
        </span>
      </div>

      ${afspraak.locatie ? `<p class="kaart__regel"><span aria-hidden="true">📍</span> ${veilig(afspraak.locatie)}</p>` : ""}
      ${
        klant?.telefoon
          ? `<p class="kaart__regel"><span aria-hidden="true">📞</span> <a href="${telHref(klant.telefoon)}">${veilig(klant.telefoon)}</a></p>`
          : ""
      }

      <p class="badges">
        ${omzetBadge(afspraak.omzet)}
        ${
          afspraak.verplaatstVan
            ? `<span class="badge badge--info" title="Stond eerder op ${veilig(dagLabel(datumVan(afspraak.verplaatstVan)))} ${tijdVan(afspraak.verplaatstVan)}">Verplaatst</span>`
            : ""
        }
      </p>

      <div class="kaart__acties">
        <button type="button" class="knop knop--klein" data-omzet="${afspraak.id}">
          ${afspraak.omzet ? "Omzet aanpassen" : "Omzet"}
        </button>
        <button type="button" class="knop knop--stil knop--klein" data-verplaats="${afspraak.id}">Verplaatsen</button>
        <button type="button" class="knop knop--kaal knop--klein" data-verwijder="${afspraak.id}">Verwijderen</button>
      </div>
    </li>
  `;
}

function omzetBadge(omzet) {
  if (!omzet) {
    return `<span class="badge badge--neutraal">Omzet nog niet geregistreerd</span>`;
  }
  if (!omzet.betaald) {
    return `<span class="badge badge--open">${euro(omzet.bedragCent)} — niet betaald</span>`;
  }
  const hoe = omzet.methode === "cash" ? "cash" : "bank";
  return `<span class="badge badge--ok">${euro(omzet.bedragCent)} — betaald (${hoe})</span>`;
}

/* ------------------------------------------------------------- dialogen */

/** Nieuwe afspraak inplannen. */
export function openAfspraakDialoog() {
  const dlg = document.getElementById("dlg-afspraak");
  const form = document.getElementById("form-afspraak");

  vulKlantKeuze(form.klantId);
  form.datum.value = vandaagISO();
  form.tijd.value = "10:00";
  form.duurMin.value = "60";
  form.behandeling.value = "";
  form.locatie.value = adresVanKlant(getKlant(form.klantId.value));

  // Bij een andere klant hoort standaard ook het adres van die klant.
  form.klantId.onchange = () => {
    form.locatie.value = adresVanKlant(getKlant(form.klantId.value));
  };

  document.getElementById("afspraak-salon").onclick = () => {
    form.locatie.value = SALON;
  };

  document.getElementById("afspraak-nieuwe-klant").onclick = () => {
    openKlantDialoog({
      onOpgeslagen: (klant) => {
        vulKlantKeuze(form.klantId, klant.id);
        form.locatie.value = adresVanKlant(klant);
      },
    });
  };

  form.onsubmit = (event) => {
    event.preventDefault();
    if (!form.klantId.value) return toonFout(dlg, "Kies eerst een klant.");
    if (!form.datum.value || !form.tijd.value) {
      return toonFout(dlg, "Vul een datum en een tijd in.");
    }
    const afspraak = voegAfspraakToe({
      klantId: form.klantId.value,
      start: `${form.datum.value}T${form.tijd.value}`,
      duurMin: Number(form.duurMin.value),
      behandeling: form.behandeling.value.trim(),
      locatie: form.locatie.value.trim(),
    });
    dlg.close();
    melding(`Afspraak met ${getKlant(afspraak.klantId).naam} ingepland`);
  };

  openDialoog(dlg);
}

/** Vult de klantenkeuzelijst; selecteert eventueel een specifieke klant. */
function vulKlantKeuze(select, geselecteerd) {
  const huidig = geselecteerd || select.value;
  const klanten = getKlanten();
  select.innerHTML = klanten.length
    ? klanten
        .map((k) => `<option value="${k.id}">${veilig(k.naam)}</option>`)
        .join("")
    : `<option value="">— nog geen klanten —</option>`;
  if (huidig && klanten.some((k) => k.id === huidig)) select.value = huidig;
}

/** Omzet vastleggen of corrigeren. */
export function openOmzetDialoog(afspraakId) {
  const dlg = document.getElementById("dlg-omzet");
  const form = document.getElementById("form-omzet");
  const afspraak = getAfspraak(afspraakId);
  if (!afspraak) return;

  const klant = getKlant(afspraak.klantId);
  const methodeVeld = document.getElementById("omzet-methode-veld");

  document.getElementById("omzet-context").textContent =
    `${klant ? klant.naam : "Afspraak"} — ${dagLabel(datumVan(afspraak.start))} ${tijdVan(afspraak.start)}`;

  form.bedrag.value = afspraak.omzet
    ? (afspraak.omzet.bedragCent / 100).toFixed(2).replace(".", ",")
    : "";
  form.betaald.checked = Boolean(afspraak.omzet?.betaald);
  methodeVeld.disabled = !form.betaald.checked;
  [...form.methode].forEach((radio) => {
    radio.checked = radio.value === afspraak.omzet?.methode;
  });

  // De betaalwijze is pas relevant zodra er daadwerkelijk betaald is.
  form.betaald.onchange = () => {
    methodeVeld.disabled = !form.betaald.checked;
  };

  form.onsubmit = (event) => {
    event.preventDefault();
    const bedragCent = naarCent(form.bedrag.value);
    if (bedragCent === null || bedragCent <= 0) {
      return toonFout(dlg, "Vul een bedrag in, bijvoorbeeld 45,00.");
    }
    const betaald = form.betaald.checked;
    const methode = [...form.methode].find((r) => r.checked)?.value || null;
    if (betaald && !methode) {
      return toonFout(dlg, "Geef aan of er via bank of cash betaald is.");
    }
    zetOmzet(afspraak.id, { bedragCent, betaald, methode });
    dlg.close();
    melding("Omzet opgeslagen");
  };

  openDialoog(dlg);
}

/** Afspraak naar een andere datum of tijd zetten. */
export function openVerplaatsDialoog(afspraakId) {
  const dlg = document.getElementById("dlg-verplaats");
  const form = document.getElementById("form-verplaats");
  const afspraak = getAfspraak(afspraakId);
  if (!afspraak) return;

  const klant = getKlant(afspraak.klantId);
  document.getElementById("verplaats-context").textContent =
    `${klant ? klant.naam : "Afspraak"} — staat nu op ${dagLabel(datumVan(afspraak.start))} ${tijdVan(afspraak.start)}`;

  form.datum.value = datumVan(afspraak.start);
  form.tijd.value = tijdVan(afspraak.start);

  form.onsubmit = (event) => {
    event.preventDefault();
    if (!form.datum.value || !form.tijd.value) {
      return toonFout(dlg, "Vul een datum en een tijd in.");
    }
    verplaatsAfspraak(afspraak.id, `${form.datum.value}T${form.tijd.value}`);
    dlg.close();
    melding("Afspraak verplaatst");
  };

  openDialoog(dlg);
}

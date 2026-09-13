/*
 * Tab "Overzicht": alles wat met geld te maken heeft, per maand.
 *
 * Bovenaan de cijfers van de gekozen maand — omzet, kosten, winst en wat er
 * nog binnen moet komen. Daaronder de kostenposten (met bon) en de
 * omzetstortingen, die je hier ook toevoegt.
 *
 * Winst is alle geregistreerde omzet van de maand min de kosten, dus ook de
 * afspraken die nog niet betaald zijn; "nog te ontvangen" staat er los naast.
 */

import {
  getKosten,
  getStortingen,
  maandTotalen,
  verwijderKosten,
  verwijderStorting,
  voegKostenToe,
  voegStortingToe,
} from "../store.js";
import {
  dagKort,
  euro,
  getal,
  maandLabel,
  maandVan,
  maandVerschuif,
  naarCent,
  vandaagISO,
  veilig,
} from "../format.js";
import { melding, openDialoog, toonFout } from "../ui.js";

// De gekozen maand blijft staan zolang de app open is.
let maand = maandVan(vandaagISO());

export function render(root) {
  const t = maandTotalen(maand);
  const kosten = getKosten({ maand });
  const stortingen = getStortingen().filter((s) => s.datum.startsWith(maand));

  root.innerHTML = `
    <div class="kop"><h2>Overzicht</h2></div>

    <div class="dagkiezer">
      <button type="button" class="knop knop--stil knop--rond" data-maand="-1" aria-label="Vorige maand">‹</button>
      <div class="dagkiezer__midden">
        <strong>${veilig(maandLabel(maand))}</strong>
        <input type="month" value="${maand}" data-maandkeuze aria-label="Kies een maand" />
      </div>
      <button type="button" class="knop knop--stil knop--rond" data-maand="1" aria-label="Volgende maand">›</button>
    </div>

    <div class="paneel paneel--totalen">
      <div class="cijfer cijfer--groot ${t.winstCent < 0 ? "cijfer--negatief" : ""}">
        <span>Winst</span>
        <strong>${euro(t.winstCent)}</strong>
      </div>
      <div class="cijfers">
        <div class="cijfer"><span>Omzet</span><strong>${euro(t.omzetCent)}</strong></div>
        <div class="cijfer"><span>Kosten</span><strong>${euro(t.kostenCent)}</strong></div>
        <div class="cijfer ${t.openCent ? "cijfer--open" : ""}">
          <span>Nog te ontvangen</span><strong>${euro(t.openCent)}</strong>
        </div>
      </div>
      <div class="cijfers">
        <div class="cijfer"><span>Cash</span><strong>${euro(t.cashCent)}</strong></div>
        <div class="cijfer"><span>Bank</span><strong>${euro(t.bankCent)}</strong></div>
        <div class="cijfer"><span>Gestort</span><strong>${euro(t.gestortCent)}</strong></div>
      </div>
      <div class="cijfers">
        <div class="cijfer"><span>Afspraken</span><strong>${t.aantalAfspraken}</strong></div>
        <div class="cijfer"><span>Kilometers</span><strong>${getal(t.km)} km</strong></div>
        <div class="cijfer"><span>Gewerkt</span><strong>${getal(t.uren, 2)} uur</strong></div>
      </div>
      <p class="hint">
        Winst is alle omzet van deze maand min de kosten, dus inclusief wat nog
        niet betaald is. Kilometers en uren komen uit de dagen die je hebt
        afgesloten (${t.afgeslotenDagen}).
      </p>
    </div>

    <div class="kop kop--sectie">
      <h3>Kosten</h3>
      <button type="button" class="knop knop--klein" data-nieuwe-kosten>+ Kosten</button>
    </div>
    ${
      kosten.length === 0
        ? `<p class="leeg">Geen kosten in deze maand.</p>`
        : `<ul class="lijst">${kosten.map(kostenRegel).join("")}</ul>`
    }

    <div class="kop kop--sectie">
      <h3>Omzetstortingen</h3>
      <button type="button" class="knop knop--klein knop--stil" data-nieuwe-storting>+ Storting</button>
    </div>
    ${
      stortingen.length === 0
        ? `<p class="leeg">Geen stortingen in deze maand.</p>`
        : `<ul class="lijst">${stortingen.map(stortingRegel).join("")}</ul>`
    }
  `;

  root.querySelectorAll("[data-maand]").forEach((knop) =>
    knop.addEventListener("click", () => {
      maand = maandVerschuif(maand, Number(knop.dataset.maand));
      render(root);
    }),
  );

  root.querySelector("[data-maandkeuze]").addEventListener("change", (event) => {
    if (!event.target.value) return;
    maand = event.target.value;
    render(root);
  });

  root.querySelector("[data-nieuwe-kosten]").addEventListener("click", openKostenDialoog);
  root.querySelector("[data-nieuwe-storting]").addEventListener("click", openStortingDialoog);

  root.querySelectorAll("[data-verwijder-kosten]").forEach((knop) =>
    knop.addEventListener("click", () => {
      verwijderKosten(knop.dataset.verwijderKosten);
      melding("Kostenpost verwijderd");
    }),
  );
  root.querySelectorAll("[data-verwijder-storting]").forEach((knop) =>
    knop.addEventListener("click", () => {
      verwijderStorting(knop.dataset.verwijderStorting);
      melding("Storting verwijderd");
    }),
  );
}

function kostenRegel(post) {
  return `
    <li class="kaart kaart--regel">
      <div>
        <strong>${euro(post.bedragCent)}</strong>
        <span class="kaart__regel kaart__regel--stil">
          ${veilig(post.omschrijving)} · ${veilig(dagKort(post.datum))}
        </span>
        ${post.bon ? bonChip(post.bon) : `<span class="kaart__regel kaart__regel--stil">Geen bon</span>`}
      </div>
      <button type="button" class="knop knop--kaal knop--klein" data-verwijder-kosten="${post.id}">Verwijderen</button>
    </li>
  `;
}

/** De bon als aanklikbaar chipje; zonder bestand alleen de naam. */
function bonChip(bon) {
  const naam = veilig(bon.naam);
  if (!bon.dataUrl) return `<span class="bon__chip">📎 ${naam}</span>`;
  return `<a class="bon__chip" href="${bon.dataUrl}" target="_blank" rel="noopener">📎 ${naam}</a>`;
}

function stortingRegel(storting) {
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

/* ------------------------------------------------------------- dialogen */

function openKostenDialoog() {
  const dlg = document.getElementById("dlg-kosten");
  const form = document.getElementById("form-kosten");
  const preview = document.getElementById("kosten-bon-preview");

  form.reset();
  form.datum.value = standaardDatum();
  preview.hidden = true;
  preview.innerHTML = "";

  // De bon wordt als data-URL in het geheugen bewaard; er gaat niets naar een
  // server. Later komt hier de upload naar Google Drive.
  let bon = null;
  form.bon.onchange = () => {
    const bestand = form.bon.files[0];
    if (!bestand) {
      bon = null;
      preview.hidden = true;
      preview.innerHTML = "";
      return;
    }
    const lezer = new FileReader();
    lezer.onload = () => {
      bon = { naam: bestand.name, type: bestand.type, dataUrl: lezer.result };
      preview.hidden = false;
      preview.innerHTML = bestand.type.startsWith("image/")
        ? `<img src="${lezer.result}" alt="Bon ${veilig(bestand.name)}" /><span>${veilig(bestand.name)}</span>`
        : `<span class="bon__chip">📎 ${veilig(bestand.name)}</span>`;
    };
    lezer.readAsDataURL(bestand);
  };

  form.onsubmit = (event) => {
    event.preventDefault();
    const bedragCent = naarCent(form.bedrag.value);
    if (bedragCent === null || bedragCent <= 0) {
      return toonFout(dlg, "Vul een bedrag in, bijvoorbeeld 89,95.");
    }
    if (!form.omschrijving.value.trim()) {
      return toonFout(dlg, "Vul in waarvoor de kosten waren.");
    }
    if (!form.datum.value) return toonFout(dlg, "Kies een datum.");

    voegKostenToe({
      datum: form.datum.value,
      omschrijving: form.omschrijving.value.trim(),
      bedragCent,
      bon,
    });
    maand = maandVan(form.datum.value);
    dlg.close();
    melding("Kosten toegevoegd");
  };

  openDialoog(dlg);
}

function openStortingDialoog() {
  const dlg = document.getElementById("dlg-storting");
  const form = document.getElementById("form-storting");

  form.reset();
  form.datum.value = standaardDatum();

  form.onsubmit = (event) => {
    event.preventDefault();
    const bedragCent = naarCent(form.bedrag.value);
    if (bedragCent === null || bedragCent <= 0) {
      return toonFout(dlg, "Vul een bedrag in, bijvoorbeeld 120,00.");
    }
    if (!form.datum.value) return toonFout(dlg, "Kies een datum.");

    voegStortingToe({ datum: form.datum.value, bedragCent });
    maand = maandVan(form.datum.value);
    dlg.close();
    melding("Storting toegevoegd");
  };

  openDialoog(dlg);
}

/** Vandaag, of de eerste van de maand die je aan het bekijken bent. */
function standaardDatum() {
  const vandaag = vandaagISO();
  return maandVan(vandaag) === maand ? vandaag : `${maand}-01`;
}

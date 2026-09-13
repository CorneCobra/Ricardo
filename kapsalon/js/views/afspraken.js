/*
 * Tab "Afspraken": het startscherm, in twee weergaven.
 *
 * - Lijst: alle komende afspraken per dag, met wie, waar, hoe laat, het
 *   telefoonnummer en de omzetstatus.
 * - Dag: een tijdlijn van één dag. Tik op een vrije plek om daar meteen een
 *   afspraak in te plannen, of op een blok om er iets mee te doen.
 *
 * Bij het inplannen en verplaatsen wordt gecontroleerd of de afspraak niet
 * over een bestaande heen valt.
 */

import {
  DAG_EINDE,
  DAG_START,
  afsprakenOp,
  getAfgelopenAfspraken,
  getAfspraak,
  getKlant,
  getKlanten,
  getKomendeAfspraken,
  overlapMet,
  plaatsVanKlant,
  tijdvakVan,
  verplaatsAfspraak,
  verwijderAfspraak,
  voegAfspraakToe,
  vrijeSlots,
  zetOmzet,
} from "../store.js";
import { SALON } from "../data.js";
import {
  dagLabel,
  datumVan,
  duurLabel,
  euro,
  naarCent,
  naarISODatum,
  tijdVan,
  tijdVanMinuten,
  tijdvak,
  telHref,
  vandaagISO,
  veilig,
} from "../format.js";
import { melding, openDialoog, toonFout } from "../ui.js";
import { openKlantDialoog } from "./klanten.js";

// Blijft bewaard zolang de app open staat, zodat weergave, filter en gekozen
// dag niet terugspringen bij elke wijziging.
let weergave = "lijst"; // "lijst" | "dag"
let toonAfgelopen = false;
let agendaDatum = vandaagISO();

/** Hoogte van één minuut in de dagagenda. */
const PX_PER_MINUUT = 1.05;

export function render(root) {
  root.innerHTML = `
    <div class="kop">
      <h2>Afspraken</h2>
      <button type="button" class="knop" data-nieuwe-afspraak>+ Nieuwe afspraak</button>
    </div>

    <div class="wissel" role="group" aria-label="Weergave">
      <button type="button" class="wissel__knop ${weergave === "lijst" ? "wissel__knop--actief" : ""}" data-weergave="lijst">Lijst</button>
      <button type="button" class="wissel__knop ${weergave === "dag" ? "wissel__knop--actief" : ""}" data-weergave="dag">Dag</button>
    </div>

    <div data-inhoud></div>
  `;

  const inhoud = root.querySelector("[data-inhoud]");
  if (weergave === "lijst") tekenLijst(inhoud, root);
  else tekenDag(inhoud, root);

  root.querySelector("[data-nieuwe-afspraak]").addEventListener("click", () => {
    openAfspraakDialoog({ datum: weergave === "dag" ? agendaDatum : vandaagISO() });
  });

  root.querySelectorAll("[data-weergave]").forEach((knop) =>
    knop.addEventListener("click", () => {
      weergave = knop.dataset.weergave;
      render(root);
    }),
  );
}

/* ------------------------------------------------------------ lijstweergave */

function tekenLijst(inhoud, root) {
  const komend = getKomendeAfspraken();
  const afgelopen = toonAfgelopen ? getAfgelopenAfspraken() : [];

  inhoud.innerHTML = `
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

  inhoud.querySelector("[data-filter]").addEventListener("change", (event) => {
    toonAfgelopen = event.target.checked;
    render(root);
  });

  koppelKaartknoppen(inhoud);
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

export function omzetBadge(omzet) {
  if (!omzet) {
    return `<span class="badge badge--neutraal">Omzet nog niet geregistreerd</span>`;
  }
  if (!omzet.betaald) {
    return `<span class="badge badge--open">${euro(omzet.bedragCent)} — niet betaald</span>`;
  }
  const hoe = omzet.methode === "cash" ? "cash" : "bank";
  return `<span class="badge badge--ok">${euro(omzet.bedragCent)} — betaald (${hoe})</span>`;
}

/** Koppelt de knoppen Omzet / Verplaatsen / Verwijderen binnen een stuk HTML. */
export function koppelKaartknoppen(wortel) {
  wortel.querySelectorAll("[data-omzet]").forEach((knop) =>
    knop.addEventListener("click", () => openOmzetDialoog(knop.dataset.omzet)),
  );
  wortel.querySelectorAll("[data-verplaats]").forEach((knop) =>
    knop.addEventListener("click", () => openVerplaatsDialoog(knop.dataset.verplaats)),
  );
  wortel.querySelectorAll("[data-verwijder]").forEach((knop) =>
    knop.addEventListener("click", () => vraagVerwijderen(knop.dataset.verwijder)),
  );
}

function vraagVerwijderen(id) {
  const afspraak = getAfspraak(id);
  if (!afspraak) return;
  const klant = getKlant(afspraak.klantId);
  if (confirm(`Afspraak met ${klant ? klant.naam : "deze klant"} verwijderen?`)) {
    verwijderAfspraak(id);
    melding("Afspraak verwijderd");
  }
}

/* -------------------------------------------------------------- dagagenda */

function tekenDag(inhoud, root) {
  const afspraken = afsprakenOp(agendaDatum);
  const hoogte = (DAG_EINDE - DAG_START) * PX_PER_MINUUT;

  const uren = [];
  for (let m = DAG_START; m <= DAG_EINDE; m += 60) {
    uren.push(`
      <div class="agenda__uur" style="top:${(m - DAG_START) * PX_PER_MINUUT}px">
        <span>${tijdVanMinuten(m)}</span>
      </div>
    `);
  }

  inhoud.innerHTML = `
    ${dagKiezer(agendaDatum)}

    <p class="agenda__hint">
      ${
        afspraken.length
          ? `${afspraken.length} ${afspraken.length === 1 ? "afspraak" : "afspraken"} — tik op een vrije plek om in te plannen.`
          : "Nog niets gepland. Tik op een tijdstip om een afspraak te maken."
      }
    </p>

    <div class="agenda" style="height:${hoogte}px">
      <div class="agenda__raster" data-raster>${uren.join("")}</div>
      ${afspraken.map(blok).join("")}
    </div>
  `;

  koppelDagKiezer(inhoud, root);

  // Tikken op een lege plek: afronden op een kwartier en meteen inplannen.
  inhoud.querySelector("[data-raster]").addEventListener("click", (event) => {
    const vlak = event.currentTarget.getBoundingClientRect();
    const minuten = DAG_START + (event.clientY - vlak.top) / PX_PER_MINUUT;
    const afgerond = Math.max(DAG_START, Math.floor(minuten / 15) * 15);
    openAfspraakDialoog({ datum: agendaDatum, tijd: tijdVanMinuten(afgerond) });
  });

  inhoud.querySelectorAll("[data-blok]").forEach((el) =>
    el.addEventListener("click", () => openActieDialoog(el.dataset.blok)),
  );
}

function blok(afspraak) {
  const klant = getKlant(afspraak.klantId);
  const vak = tijdvakVan(afspraak);
  const top = (vak.begin - DAG_START) * PX_PER_MINUUT;
  const hoogte = Math.max(28, (vak.einde - vak.begin) * PX_PER_MINUUT);
  const kort = hoogte < 52;
  const status = !afspraak.omzet ? "" : afspraak.omzet.betaald ? "blok--betaald" : "blok--open";

  return `
    <button type="button" class="blok ${status} ${kort ? "blok--kort" : ""}"
      style="top:${top}px;height:${hoogte}px" data-blok="${afspraak.id}">
      <span class="blok__tijd">${tijdVan(afspraak.start)}</span>
      <span class="blok__naam">${veilig(klant ? klant.naam : "Onbekende klant")}</span>
      ${
        kort
          ? ""
          : `<span class="blok__detail">${veilig([afspraak.behandeling, afspraak.locatie].filter(Boolean).join(" · "))}</span>`
      }
    </button>
  `;
}

/** Kop met pijltjes om een dag terug of vooruit te bladeren. */
function dagKiezer(datum) {
  return `
    <div class="dagkiezer">
      <button type="button" class="knop knop--stil knop--rond" data-dag="-1" aria-label="Vorige dag">‹</button>
      <div class="dagkiezer__midden">
        <strong>${veilig(dagLabel(datum))}</strong>
        <input type="date" value="${datum}" data-dagdatum aria-label="Kies een dag" />
      </div>
      <button type="button" class="knop knop--stil knop--rond" data-dag="1" aria-label="Volgende dag">›</button>
    </div>
  `;
}

function koppelDagKiezer(inhoud, root) {
  inhoud.querySelectorAll("[data-dag]").forEach((knop) =>
    knop.addEventListener("click", () => {
      const d = new Date(`${agendaDatum}T12:00`);
      d.setDate(d.getDate() + Number(knop.dataset.dag));
      agendaDatum = naarISODatum(d);
      render(root);
    }),
  );
  inhoud.querySelector("[data-dagdatum]").addEventListener("change", (event) => {
    if (!event.target.value) return;
    agendaDatum = event.target.value;
    render(root);
  });
}

/* ------------------------------------------------------------- dialogen */

/** Nieuwe afspraak inplannen, eventueel met een tijdstip uit de agenda. */
export function openAfspraakDialoog({ datum = vandaagISO(), tijd = "10:00" } = {}) {
  const dlg = document.getElementById("dlg-afspraak");
  const form = document.getElementById("form-afspraak");

  vulKlantKeuze(form.klantId);
  form.datum.value = datum;
  form.tijd.value = tijd;
  form.duurMin.value = "60";
  form.behandeling.value = "";
  form.locatie.value = plaatsVanKlant(getKlant(form.klantId.value));

  const toonRuimte = () =>
    werkRuimteBij({
      datum: form.datum.value,
      duurMin: Number(form.duurMin.value),
      overzichtEl: document.getElementById("afspraak-dagoverzicht"),
      slotsEl: document.getElementById("afspraak-slots"),
      rijEl: document.getElementById("afspraak-slots-rij"),
      kiesTijd: (gekozen) => {
        form.tijd.value = gekozen;
      },
    });

  // Bij een andere klant hoort standaard ook de plaats van die klant.
  form.klantId.onchange = () => {
    form.locatie.value = plaatsVanKlant(getKlant(form.klantId.value));
  };
  form.datum.onchange = toonRuimte;
  form.duurMin.onchange = toonRuimte;

  document.getElementById("afspraak-salon").onclick = () => {
    form.locatie.value = SALON;
  };

  document.getElementById("afspraak-nieuwe-klant").onclick = () => {
    openKlantDialoog({
      onOpgeslagen: (klant) => {
        vulKlantKeuze(form.klantId, klant.id);
        form.locatie.value = plaatsVanKlant(klant);
      },
    });
  };

  let bevestigd = "";
  form.onsubmit = (event) => {
    event.preventDefault();
    if (!form.klantId.value) return toonFout(dlg, "Kies eerst een klant.");
    if (!form.datum.value || !form.tijd.value) {
      return toonFout(dlg, "Vul een datum en een tijd in.");
    }

    const sleutel = `${form.datum.value}T${form.tijd.value}-${form.duurMin.value}`;
    const botsing = overlapMet({
      datum: form.datum.value,
      tijd: form.tijd.value,
      duurMin: Number(form.duurMin.value),
    });
    if (botsing.length && bevestigd !== sleutel) {
      bevestigd = sleutel;
      return toonFout(dlg, `${botsingTekst(botsing)} Klik nogmaals op Opslaan om het tóch in te plannen.`);
    }

    const afspraak = voegAfspraakToe({
      klantId: form.klantId.value,
      start: `${form.datum.value}T${form.tijd.value}`,
      duurMin: Number(form.duurMin.value),
      behandeling: form.behandeling.value.trim(),
      locatie: form.locatie.value.trim(),
    });
    dlg.close();
    agendaDatum = datumVan(afspraak.start);
    melding(`Afspraak met ${getKlant(afspraak.klantId).naam} ingepland`);
  };

  openDialoog(dlg);
  toonRuimte();
}

/** Wat staat er al op die dag, en waar is nog ruimte? */
function werkRuimteBij({ datum, duurMin, negeerId = null, overzichtEl, slotsEl, rijEl, kiesTijd }) {
  const bezet = afsprakenOp(datum).filter((a) => a.id !== negeerId);
  overzichtEl.textContent = bezet.length
    ? `Al gepland: ${bezet
        .map((a) => `${tijdvak(a.start, a.duurMin)} ${getKlant(a.klantId)?.naam || "?"}`)
        .join(" · ")}`
    : "Er staat nog niets op deze dag.";

  const slots = vrijeSlots(datum, duurMin, { negeerId });
  if (!bezet.length || !slots.length) {
    slotsEl.hidden = true;
    rijEl.innerHTML = "";
    return;
  }
  slotsEl.hidden = false;
  rijEl.innerHTML = slots
    .map((t) => `<button type="button" class="slot" data-slot="${t}">${t}</button>`)
    .join("");
  rijEl.querySelectorAll("[data-slot]").forEach((knop) =>
    knop.addEventListener("click", () => kiesTijd(knop.dataset.slot)),
  );
}

function botsingTekst(botsing) {
  const namen = botsing
    .map((a) => `${getKlant(a.klantId)?.naam || "een afspraak"} (${tijdvak(a.start, a.duurMin)})`)
    .join(" en ");
  return `Let op: dit overlapt met ${namen}.`;
}

/** Vult de klantenkeuzelijst; selecteert eventueel een specifieke klant. */
function vulKlantKeuze(select, geselecteerd) {
  const huidig = geselecteerd || select.value;
  const klanten = getKlanten();
  select.innerHTML = klanten.length
    ? klanten.map((k) => `<option value="${k.id}">${veilig(k.naam)}</option>`).join("")
    : `<option value="">— nog geen klanten —</option>`;
  if (huidig && klanten.some((k) => k.id === huidig)) select.value = huidig;
}

/** Klein keuzemenu bij het tikken op een blok in de dagagenda. */
export function openActieDialoog(afspraakId) {
  const dlg = document.getElementById("dlg-acties");
  const afspraak = getAfspraak(afspraakId);
  if (!afspraak) return;
  const klant = getKlant(afspraak.klantId);

  document.getElementById("acties-titel").textContent = klant ? klant.naam : "Afspraak";
  document.getElementById("acties-context").textContent = [
    tijdvak(afspraak.start, afspraak.duurMin),
    afspraak.behandeling,
    afspraak.locatie,
    klant?.telefoon,
  ]
    .filter(Boolean)
    .join(" · ");

  dlg.querySelectorAll("[data-actie]").forEach((knop) => {
    knop.onclick = () => {
      dlg.close();
      if (knop.dataset.actie === "omzet") openOmzetDialoog(afspraak.id);
      if (knop.dataset.actie === "verplaats") openVerplaatsDialoog(afspraak.id);
      if (knop.dataset.actie === "verwijder") vraagVerwijderen(afspraak.id);
    };
  });

  openDialoog(dlg);
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
    `${klant ? klant.naam : "Afspraak"} — staat nu op ${dagLabel(datumVan(afspraak.start))} ${tijdvak(afspraak.start, afspraak.duurMin)}`;

  form.datum.value = datumVan(afspraak.start);
  form.tijd.value = tijdVan(afspraak.start);

  const toonRuimte = () =>
    werkRuimteBij({
      datum: form.datum.value,
      duurMin: afspraak.duurMin,
      negeerId: afspraak.id,
      overzichtEl: document.getElementById("verplaats-dagoverzicht"),
      slotsEl: document.getElementById("verplaats-slots"),
      rijEl: document.getElementById("verplaats-slots-rij"),
      kiesTijd: (gekozen) => {
        form.tijd.value = gekozen;
      },
    });
  form.datum.onchange = toonRuimte;

  let bevestigd = "";
  form.onsubmit = (event) => {
    event.preventDefault();
    if (!form.datum.value || !form.tijd.value) {
      return toonFout(dlg, "Vul een datum en een tijd in.");
    }

    const sleutel = `${form.datum.value}T${form.tijd.value}`;
    const botsing = overlapMet({
      datum: form.datum.value,
      tijd: form.tijd.value,
      duurMin: afspraak.duurMin,
      negeerId: afspraak.id,
    });
    if (botsing.length && bevestigd !== sleutel) {
      bevestigd = sleutel;
      return toonFout(dlg, `${botsingTekst(botsing)} Klik nogmaals op Verplaatsen om het tóch te doen.`);
    }

    verplaatsAfspraak(afspraak.id, `${form.datum.value}T${form.tijd.value}`);
    dlg.close();
    agendaDatum = form.datum.value;
    melding("Afspraak verplaatst");
  };

  openDialoog(dlg);
  toonRuimte();
}

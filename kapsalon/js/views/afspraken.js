/*
 * Tab "Afspraken": het startscherm, in twee weergaven.
 *
 * - Lijst: alle komende afspraken per dag, met wie, waar, hoe laat, een
 *   WhatsApp-knop en de omzetstatus.
 * - Dag: een tijdlijn van één dag. Tik op een vrije plek om daar meteen een
 *   afspraak in te plannen.
 *
 * Tikken op een afspraak opent één werkscherm waarin je de omzet en de
 * betaling vastlegt én direct een vervolgafspraak plant.
 */

import {
  DAG_EINDE,
  DAG_START,
  afsprakenOp,
  getAfgelopenAfspraken,
  getAfspraak,
  getKlant,
  getKlanten,
  getAfsluiting,
  getKomendeAfspraken,
  omzetTotaal,
  overlapMet,
  plaatsVanKlant,
  productenTotaal,
  tijdvakVan,
  verplaatsAfspraak,
  verwijderAfspraak,
  vorigeNotities,
  wijzigAfspraak,
  wijzigKlant,
  voegAfspraakToe,
  vrijeSlots,
  zetOmzet,
} from "../store.js";
import { SALON } from "../data.js";
import {
  dagKort,
  dagLabel,
  datumVan,
  duurLabel,
  euro,
  naarCent,
  naarISODatum,
  tijdVan,
  tijdVanMinuten,
  tijdvak,
  vandaagISO,
  veilig,
  whatsappHref,
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

/** Snelkeuzes voor een vervolgafspraak. */
const VERVOLG_WEKEN = [1, 2, 3, 4, 6, 8, 12];

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

  koppelAfspraakKlik(inhoud);
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
    <li class="kaart kaart--afspraak kaart--klikbaar ${isVerleden ? "kaart--verleden" : ""}"
        data-afspraak="${afspraak.id}" tabindex="0" role="button"
        aria-label="Afspraak met ${veilig(naam)} openen">
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
      ${klant?.telefoon ? whatsappKnop(klant) : ""}

      <p class="badges">
        ${omzetBadge(afspraak.omzet)}
        ${
          afspraak.verplaatstVan
            ? `<span class="badge badge--info" title="Stond eerder op ${veilig(dagLabel(datumVan(afspraak.verplaatstVan)))} ${tijdVan(afspraak.verplaatstVan)}">Verplaatst</span>`
            : ""
        }
      </p>
    </li>
  `;
}

/** Groene WhatsApp-knop die de chat met een leeg bericht opent. */
export function whatsappKnop(klant) {
  return `
    <a class="wa" href="${whatsappHref(klant.telefoon)}" target="_blank" rel="noopener"
       aria-label="WhatsApp ${veilig(klant.naam)}">
      ${WA_ICOON}
      <span>${veilig(klant.telefoon)}</span>
    </a>
  `;
}

const WA_ICOON = `
  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
    <path d="M12 2a10 10 0 0 0-8.7 14.9L2 22l5.3-1.3A10 10 0 1 0 12 2Zm0 2a8 8 0 1 1-4.1 14.9l-.4-.2-2.6.6.7-2.5-.2-.4A8 8 0 0 1 12 4Z"/>
    <path d="M9.2 7.6c-.2-.4-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.4-.3.3-.9.9-.9 2.1s.9 2.4 1 2.6c.1.2 1.7 2.8 4.3 3.8 2.1.8 2.6.7 3 .6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2 0-.1-.2-.2-.5-.3l-1.7-.8c-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1-.3-.1-1.2-.4-2.2-1.4-.8-.7-1.4-1.6-1.5-1.8-.1-.2 0-.4.1-.5l.4-.5c.1-.2.2-.3.3-.5 0-.2 0-.3 0-.5l-.7-1.6Z"/>
  </svg>
`;

export function omzetBadge(omzet) {
  if (!omzet) {
    return `<span class="badge badge--neutraal">Omzet nog niet geregistreerd</span>`;
  }
  const totaal = euro(omzetTotaal(omzet));
  const aantal = (omzet.producten || []).length;
  const producten = aantal
    ? `<span class="badge badge--info" title="${aantal === 1 ? "1 product" : `${aantal} producten`} voor ${euro(productenTotaal(omzet))}">
         + ${euro(productenTotaal(omzet))} product${aantal === 1 ? "" : "en"}
       </span>`
    : "";
  const hoofd = omzet.betaald
    ? `<span class="badge badge--ok">${totaal} — betaald (${omzet.methode === "cash" ? "cash" : "bank"})</span>`
    : `<span class="badge badge--open">${totaal} — niet betaald</span>`;
  return hoofd + producten;
}

/**
 * Maakt elke kaart met data-afspraak aanklikbaar. Klikken op de WhatsApp-knop
 * telt niet als "kaart openen".
 */
export function koppelAfspraakKlik(wortel) {
  wortel.querySelectorAll("[data-afspraak]").forEach((kaartEl) => {
    kaartEl.addEventListener("click", (event) => {
      if (event.target.closest("a, button")) return;
      openAfspraakDetail(kaartEl.dataset.afspraak);
    });
    kaartEl.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      if (event.target.closest("a, button")) return;
      event.preventDefault();
      openAfspraakDetail(kaartEl.dataset.afspraak);
    });
  });
}

function vraagVerwijderen(id) {
  const afspraak = getAfspraak(id);
  if (!afspraak) return;
  const klant = getKlant(afspraak.klantId);
  const totaal = omzetTotaal(afspraak.omzet);
  // De omzet hangt aan de afspraak, dus die verdwijnt mee uit je cijfers.
  const waarschuwing = totaal
    ? `\n\nLet op: de omzet van ${euro(totaal)} verdwijnt dan ook uit je dag- en maandcijfers.`
    : "";
  if (confirm(`Afspraak met ${klant ? klant.naam : "deze klant"} verwijderen?${waarschuwing}`)) {
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
    el.addEventListener("click", () => openAfspraakDetail(el.dataset.blok)),
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

/* ------------------------------------------------- het afspraakwerkscherm */

/**
 * Eén scherm voor een bestaande afspraak: omzet en betaling vastleggen en
 * meteen een vervolgafspraak plannen. Verplaatsen en verwijderen zitten
 * onderin.
 */
export function openAfspraakDetail(afspraakId) {
  const dlg = document.getElementById("dlg-detail");
  const form = document.getElementById("form-detail");
  const afspraak = getAfspraak(afspraakId);
  if (!afspraak) return;

  const klant = getKlant(afspraak.klantId);
  const betalingRij = document.getElementById("detail-betaling");
  const vervolgAan = document.getElementById("detail-vervolg");
  const vervolgVelden = document.getElementById("detail-vervolg-velden");

  document.getElementById("detail-titel").textContent = klant ? klant.naam : "Afspraak";
  document.getElementById("detail-context").textContent = [
    `${dagLabel(datumVan(afspraak.start))} ${tijdvak(afspraak.start, afspraak.duurMin)}`,
    afspraak.behandeling,
    afspraak.locatie,
  ]
    .filter(Boolean)
    .join(" · ");
  document.getElementById("detail-contact").innerHTML = klant?.telefoon
    ? whatsappKnop(klant)
    : "";

  // --- notities: deze afspraak, de klant, en wat er vorige keren stond
  form.notitie.value = afspraak.notitie || "";
  form.klantnotitie.value = klant?.notitie || "";

  const vorige = vorigeNotities(afspraak.klantId, afspraak.start);
  const vorigeVeld = document.getElementById("detail-vorige-veld");
  vorigeVeld.hidden = vorige.length === 0;
  document.getElementById("detail-vorige").innerHTML = vorige.length
    ? `<ul class="notities">${vorige
        .map(
          (a) => `
            <li>
              <span class="notities__kop">${veilig(dagKort(datumVan(a.start)))}${a.behandeling ? ` · ${veilig(a.behandeling)}` : ""}</span>
              <span>${veilig(a.notitie)}</span>
            </li>`,
        )
        .join("")}</ul>`
    : "";

  // --- producten (losse verkopen bij deze afspraak)
  let producten = (afspraak.omzet?.producten || []).map((p) => ({ ...p }));
  const productenLijst = document.getElementById("detail-producten");
  const productNaam = document.getElementById("detail-product-naam");
  const productBedrag = document.getElementById("detail-product-bedrag");
  const totaalHint = document.getElementById("detail-totaal");

  const tekenProducten = () => {
    productenLijst.innerHTML = producten.length
      ? producten
          .map(
            (p, i) => `
              <li class="product">
                <span>${veilig(p.omschrijving)}</span>
                <strong>${euro(p.bedragCent)}</strong>
                <button type="button" class="knop knop--kaal knop--klein" data-product-weg="${i}"
                  aria-label="${veilig(p.omschrijving)} verwijderen">✕</button>
              </li>`,
          )
          .join("")
      : "";
    productenLijst.querySelectorAll("[data-product-weg]").forEach((knop) =>
      knop.addEventListener("click", () => {
        producten.splice(Number(knop.dataset.productWeg), 1);
        tekenProducten();
      }),
    );
    werkTotaalBij();
  };

  const werkTotaalBij = () => {
    const behandeling = naarCent(form.bedrag.value) || 0;
    const productenSom = producten.reduce((som, p) => som + p.bedragCent, 0);
    totaalHint.textContent = productenSom
      ? `Totaal: ${euro(behandeling + productenSom)} (behandeling ${euro(behandeling)} + producten ${euro(productenSom)})`
      : "";
  };

  const voegProductToe = () => {
    const omschrijving = productNaam.value.trim();
    const bedragCent = naarCent(productBedrag.value);
    if (!omschrijving || bedragCent === null || bedragCent <= 0) {
      return toonFout(dlg, "Vul een product en een bedrag in, bijvoorbeeld Shampoo en 14,95.");
    }
    producten.push({ omschrijving, bedragCent });
    productNaam.value = "";
    productBedrag.value = "";
    productNaam.focus();
    tekenProducten();
  };

  document.getElementById("detail-product-toevoegen").onclick = voegProductToe;
  // Enter in de productvelden voegt toe in plaats van het formulier te versturen.
  [productNaam, productBedrag].forEach((veld) => {
    veld.value = "";
    veld.onkeydown = (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      voegProductToe();
    };
  });

  // --- omzet en betaling
  form.bedrag.oninput = werkTotaalBij;
  form.bedrag.value = afspraak.omzet
    ? (afspraak.omzet.bedragCent / 100).toFixed(2).replace(".", ",")
    : "";
  // Eén tik: nog niet betaald, cash of bank.
  let betaling = afspraak.omzet?.betaald ? afspraak.omzet.methode || "bank" : "open";
  const tekenBetaling = () => {
    betalingRij.querySelectorAll("[data-betaling]").forEach((knop) => {
      const actief = knop.dataset.betaling === betaling;
      knop.classList.toggle("keuzeknop--actief", actief);
      knop.classList.toggle(`keuzeknop--${knop.dataset.betaling}`, actief);
      knop.setAttribute("aria-checked", String(actief));
    });
  };
  betalingRij.querySelectorAll("[data-betaling]").forEach((knop) => {
    knop.onclick = () => {
      betaling = knop.dataset.betaling;
      tekenBetaling();
    };
  });
  tekenBetaling();
  tekenProducten();

  // --- vervolgafspraak
  vervolgAan.checked = false;
  vervolgVelden.hidden = true;
  form.datum.value = "";
  form.tijd.value = tijdVan(afspraak.start);
  form.duurMin.value = String(afspraak.duurMin || 60);

  const toonRuimte = () => {
    if (!form.datum.value) {
      document.getElementById("detail-dagoverzicht").textContent = "";
      document.getElementById("detail-slots").hidden = true;
      return;
    }
    werkRuimteBij({
      datum: form.datum.value,
      duurMin: Number(form.duurMin.value),
      overzichtEl: document.getElementById("detail-dagoverzicht"),
      slotsEl: document.getElementById("detail-slots"),
      rijEl: document.getElementById("detail-slots-rij"),
      kiesTijd: (gekozen) => {
        form.tijd.value = gekozen;
      },
    });
  };

  // Weken-knopjes: zelfde dag van de week, zelfde tijd, n weken later.
  const wekenRij = document.getElementById("detail-weken");
  wekenRij.innerHTML = VERVOLG_WEKEN.map(
    (w) => `<button type="button" class="slot" data-weken="${w}">${w} wk</button>`,
  ).join("");
  wekenRij.querySelectorAll("[data-weken]").forEach((knop) =>
    knop.addEventListener("click", () => {
      const d = new Date(`${datumVan(afspraak.start)}T12:00`);
      d.setDate(d.getDate() + Number(knop.dataset.weken) * 7);
      form.datum.value = naarISODatum(d);
      wekenRij.querySelectorAll("[data-weken]").forEach((k) => k.classList.remove("slot--actief"));
      knop.classList.add("slot--actief");
      toonRuimte();
    }),
  );

  vervolgAan.onchange = () => {
    vervolgVelden.hidden = !vervolgAan.checked;
    if (vervolgAan.checked && !form.datum.value) {
      // Standaard zes weken later; dat is het meest gekozen ritme.
      wekenRij.querySelector('[data-weken="6"]')?.click();
    }
  };
  form.datum.onchange = toonRuimte;
  form.duurMin.onchange = toonRuimte;

  // --- onderin: verplaatsen en verwijderen
  dlg.querySelector("[data-detail-verplaats]").onclick = () => {
    dlg.close();
    openVerplaatsDialoog(afspraak.id);
  };
  dlg.querySelector("[data-detail-verwijder]").onclick = () => {
    dlg.close();
    vraagVerwijderen(afspraak.id);
  };

  let bevestigd = "";
  form.onsubmit = (event) => {
    event.preventDefault();
    const gedaan = [];

    // Omzet is optioneel: een lege afspraak in de toekomst hoeft nog niets.
    const bedragIngevuld = form.bedrag.value.trim() !== "";
    const betaald = betaling !== "open";
    const methode = betaald ? betaling : null;

    if (betaald && !bedragIngevuld && producten.length === 0) {
      return toonFout(dlg, "Vul het bedrag in dat betaald is.");
    }
    if (bedragIngevuld || producten.length) {
      const bedragCent = bedragIngevuld ? naarCent(form.bedrag.value) : 0;
      if (bedragCent === null || (bedragIngevuld && bedragCent <= 0)) {
        return toonFout(dlg, "Vul een bedrag in, bijvoorbeeld 45,00.");
      }
      if (betaald && !methode) {
        return toonFout(dlg, "Geef aan of er via bank of cash betaald is.");
      }
      zetOmzet(afspraak.id, { bedragCent, producten, betaald, methode });
      gedaan.push(
        producten.length
          ? `omzet opgeslagen (incl. ${producten.length} product${producten.length === 1 ? "" : "en"})`
          : "omzet opgeslagen",
      );
    }

    if (vervolgAan.checked) {
      if (!form.datum.value || !form.tijd.value) {
        return toonFout(dlg, "Kies een datum en tijd voor de vervolgafspraak.");
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
      const vervolg = voegAfspraakToe({
        klantId: afspraak.klantId,
        start: `${form.datum.value}T${form.tijd.value}`,
        duurMin: Number(form.duurMin.value),
        behandeling: afspraak.behandeling,
        locatie: afspraak.locatie,
      });
      agendaDatum = datumVan(vervolg.start);
      gedaan.push(`vervolgafspraak op ${dagLabel(datumVan(vervolg.start))} ${tijdVan(vervolg.start)}`);
    }

    // Notities worden altijd meegenomen, ook als er verder niets verandert.
    const nieuweNotitie = form.notitie.value.trim();
    const nieuweKlantnotitie = form.klantnotitie.value.trim();
    if (nieuweNotitie !== (afspraak.notitie || "")) {
      wijzigAfspraak(afspraak.id, { notitie: nieuweNotitie });
      gedaan.push("notitie opgeslagen");
    }
    if (klant && nieuweKlantnotitie !== (klant.notitie || "")) {
      wijzigKlant(klant.id, { notitie: nieuweKlantnotitie });
      if (!gedaan.includes("notitie opgeslagen")) gedaan.push("klantnotitie opgeslagen");
    }

    dlg.close();
    melding(gedaan.length ? hoofdletter(gedaan.join(" · ")) : "Niets gewijzigd");
  };

  openDialoog(dlg);
}

function hoofdletter(tekst) {
  return tekst.charAt(0).toUpperCase() + tekst.slice(1);
}

/* --------------------------------------------------- plannen en verplaatsen */

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

  // De omzet hangt aan de afspraak en verhuist dus mee naar de nieuwe dag.
  const gevolgen = document.getElementById("verplaats-gevolgen");
  const toonGevolgen = () => {
    const regels = [];
    const totaal = omzetTotaal(afspraak.omzet);
    const oudeDatum = datumVan(afspraak.start);
    if (totaal && form.datum.value !== oudeDatum) {
      regels.push(`De omzet van ${euro(totaal)} telt daarna mee op de nieuwe dag.`);
    }
    const afgesloten = [oudeDatum, form.datum.value]
      .filter((d, i, lijst) => d && lijst.indexOf(d) === i && getAfsluiting(d))
      .map((d) => dagLabel(d));
    if (afgesloten.length) {
      regels.push(
        `${afgesloten.join(" en ")} ${afgesloten.length === 1 ? "is" : "zijn"} al afgesloten; die afsluiting wordt automatisch bijgewerkt.`,
      );
    }
    gevolgen.textContent = regels.join(" ");
    gevolgen.hidden = regels.length === 0;
  };

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
  form.datum.onchange = () => {
    toonRuimte();
    toonGevolgen();
  };

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
  toonGevolgen();
}

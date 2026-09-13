/* Kleine gedeelde hulpjes voor dialogen en meldingen. */

let meldingTimer = null;

/** Korte bevestiging onderin beeld (wordt ook voorgelezen door screenreaders). */
export function melding(tekst) {
  const el = document.getElementById("melding");
  el.textContent = tekst;
  el.hidden = false;
  el.classList.add("melding--zichtbaar");
  clearTimeout(meldingTimer);
  meldingTimer = setTimeout(() => {
    el.classList.remove("melding--zichtbaar");
    el.hidden = true;
  }, 3000);
}

/** Opent een dialoog en wist een eventuele oude foutmelding. */
export function openDialoog(dlg) {
  verbergFout(dlg);
  dlg.showModal();
}

export function toonFout(dlg, tekst) {
  const el = dlg.querySelector("[data-fout]");
  if (!el) return;
  el.textContent = tekst;
  el.hidden = false;
}

export function verbergFout(dlg) {
  const el = dlg.querySelector("[data-fout]");
  if (!el) return;
  el.textContent = "";
  el.hidden = true;
}

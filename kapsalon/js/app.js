/*
 * Opstart van de app: tabnavigatie en het opnieuw tekenen van het actieve
 * tabblad na elke wijziging in de store.
 */

import { subscribe } from "./store.js";
import * as afspraken from "./views/afspraken.js";
import * as klanten from "./views/klanten.js";
import * as stortingen from "./views/stortingen.js";
import * as afsluiting from "./views/dagafsluiting.js";

const views = { afspraken, klanten, stortingen, afsluiting };
const viewEl = document.getElementById("view");

let actief = "afspraken";

function teken() {
  views[actief].render(viewEl);
  document.querySelectorAll(".tab").forEach((tab) => {
    const isActief = tab.dataset.tab === actief;
    tab.classList.toggle("tab--actief", isActief);
    // aria-current vertelt hulpsoftware welk tabblad open staat.
    if (isActief) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  });
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    if (actief === tab.dataset.tab) return;
    actief = tab.dataset.tab;
    teken();
    viewEl.scrollTo?.({ top: 0 });
    window.scrollTo({ top: 0 });
  });
});

// Elke "Annuleren"-knop in een dialoog sluit gewoon zijn eigen dialoog.
document.addEventListener("click", (event) => {
  const knop = event.target.closest("[data-sluiten]");
  if (knop) knop.closest("dialog")?.close();
});

subscribe(teken);
teken();

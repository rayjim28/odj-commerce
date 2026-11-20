/* The server renders product links; this adds controls to the native scroll rails. */
(() => {
  "use strict";
  const root = document.getElementById("tm-dual-picks");
  if (!root) return;

  root.querySelectorAll("[data-pick-group]").forEach(panel => {
    const rail = panel.querySelector("[data-pick-rail]");
    const cards = [...rail.querySelectorAll("[data-pick-card]")];
    const controls = panel.querySelector("[data-pick-controls]");
    const previous = panel.querySelector('[data-pick-step="-1"]');
    const next = panel.querySelector('[data-pick-step="1"]');
    const status = panel.querySelector("[data-pick-status]");
    if (!cards.length) return;
    let announced = -1;

    const position = card => card.offsetLeft - cards[0].offsetLeft;
    function currentIndex() {
      return cards.reduce((closest, card, i) =>
        Math.abs(position(card) - rail.scrollLeft) < Math.abs(position(cards[closest]) - rail.scrollLeft)
          ? i : closest, 0);
    }
    function sync() {
      const max = Math.max(0, rail.scrollWidth - rail.clientWidth);
      controls.hidden = cards.length < 2 || max <= 2;
      previous.disabled = rail.scrollLeft <= 2;
      next.disabled = rail.scrollLeft >= max - 2;
      const index = currentIndex();
      if (index !== announced) {
        status.textContent = cards[index].dataset.pickTitle;
        announced = index;
      }
    }
    function select(index) {
      const target = Math.max(0, Math.min(cards.length - 1, index));
      rail.scrollTo({ left: position(cards[target]) });
    }
    previous.addEventListener("click", () => select(currentIndex() - 1));
    next.addEventListener("click", () => select(currentIndex() + 1));
    rail.addEventListener("scroll", sync, { passive: true });
    rail.addEventListener("keydown", event => {
      if (event.target !== rail || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const index = currentIndex();
      const targets = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: cards.length - 1 };
      if (!(event.key in targets)) return;
      event.preventDefault();
      select(targets[event.key]);
    });
    window.addEventListener("resize", sync);
    sync();
  });
})();

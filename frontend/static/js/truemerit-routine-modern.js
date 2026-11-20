/* Native collection scrolling; card content and layout also work without JS. */
(() => {
  "use strict";
  const section = document.querySelector(".tm-routine-modern");
  if (!section) return;
  const track = section.querySelector(".v71-collections-grid");
  const nav = section.querySelector(".tm-routine-nav");
  const cards = track ? [...track.querySelectorAll(".v71-collection-card")] : [];
  if (!nav || !cards.length) return;
  const previous = nav.querySelector('[data-step="-1"]');
  const next = nav.querySelector('[data-step="1"]');
  const status = section.querySelector("[data-routine-status]");
  let announced = -1;
  const position = card => card.offsetLeft - cards[0].offsetLeft;
  function currentIndex() {
    return cards.reduce((closest, card, i) =>
      Math.abs(position(card) - track.scrollLeft) < Math.abs(position(cards[closest]) - track.scrollLeft)
        ? i : closest, 0);
  }
  function update() {
    const end = Math.max(0, track.scrollWidth - track.clientWidth);
    nav.hidden = end <= 3;
    previous.disabled = track.scrollLeft <= 2;
    next.disabled = track.scrollLeft >= end - 2;
    const index = currentIndex();
    if (index !== announced) {
      status.textContent = cards[index].dataset.merchTitle;
      announced = index;
    }
  }
  function select(index) {
    const target = Math.max(0, Math.min(cards.length - 1, index));
    track.scrollTo({ left: position(cards[target]) });
  }
  previous.addEventListener("click", () => select(currentIndex() - 1));
  next.addEventListener("click", () => select(currentIndex() + 1));
  track.addEventListener("scroll", update, { passive: true });
  track.addEventListener("keydown", event => {
    if (event.target !== track || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const index = currentIndex();
    const targets = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: cards.length - 1 };
    if (!(event.key in targets)) return;
    event.preventDefault();
    select(targets[event.key]);
  });
  window.addEventListener("resize", update);
  update();
})();

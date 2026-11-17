/* All product previews stay visible. Each product card opens its details
 * on the FIRST click. Dots and arrow keys scroll a compact native carousel.
 * Do not resurrect the old fanned hidden-image implementation. */
(() => {
  "use strict";
  const stack = document.querySelector("[data-hero-stack]");
  if (!stack) return;

  const track = stack.querySelector("[data-hero-track]");
  const cards = [...stack.querySelectorAll("[data-hero-card]")];
  const dots = [...stack.querySelectorAll("[data-hero-dot]")];
  if (!track || !cards.length) return;
  let activeIndex = 0;

  function offset(index) {
    return Math.max(0, cards[index].offsetLeft - cards[0].offsetLeft);
  }
  function setActive(index) {
    activeIndex = Math.max(0, Math.min(cards.length - 1, index));
    cards.forEach((card, i) => {
      if (i === activeIndex) card.setAttribute("aria-current", "true");
      else card.removeAttribute("aria-current");
    });
    dots.forEach((dot, i) => {
      dot.setAttribute("aria-pressed", i === activeIndex ? "true" : "false");
    });
  }
  function select(index) {
    setActive(index);
    track.scrollTo({ left: offset(activeIndex), behavior: "smooth" });
  }
  dots.forEach((dot, index) => {
    dot.addEventListener("click", () => select(index));
  });
  track.addEventListener("scroll", () => {
    let nearest = 0;
    let min = Infinity;
    cards.forEach((card, i) => {
      const dist = Math.abs(offset(i) - track.scrollLeft);
      if (dist < min) { nearest = i; min = dist; }
    });
    setActive(nearest);
  }, { passive: true });
  stack.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    if (!stack.contains(document.activeElement)) return;
    event.preventDefault();
    const next = (activeIndex + (event.key === "ArrowRight" ? 1 : -1) + cards.length) % cards.length;
    select(next);
    dots[next]?.focus();
  });
  // Do not intercept clicks on product cards: all cards are visible links.
  setActive(0);
})();
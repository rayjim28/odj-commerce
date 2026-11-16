/* Progressive enhancement for the five overlapping product cards.
 * Clicking a rear card reveals it; clicking the front card opens its product page.
 * Dots and arrow keys make the same products accessible without a pointer. */
(() => {
  "use strict";
  const stack = document.querySelector("[data-hero-stack]");
  if (!stack) return;

  const cards = [...stack.querySelectorAll("[data-hero-card]")];
  const dots = [...stack.querySelectorAll("[data-hero-dot]")];
  if (!cards.length) return;
  let activeIndex = 0;

  function select(index) {
    activeIndex = (index + cards.length) % cards.length;
    cards.forEach((card, i) => {
      const slot = (i - activeIndex + cards.length) % cards.length;
      card.dataset.slot = String(slot);
      if (i === activeIndex) {
        card.setAttribute("aria-current", "true");
      } else {
        card.removeAttribute("aria-current");
      }
    });
    dots.forEach((dot, i) => {
      dot.setAttribute("aria-pressed", i === activeIndex ? "true" : "false");
    });
  }

  cards.forEach((card, index) => {
    card.addEventListener("click", (event) => {
      if (index !== activeIndex) {
        event.preventDefault();
        select(index);
      }
    });
  });

  dots.forEach((dot, index) => {
    dot.addEventListener("click", () => select(index));
  });

  stack.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    if (!stack.contains(document.activeElement)) return;
    event.preventDefault();
    select(activeIndex + (event.key === "ArrowRight" ? 1 : -1));
    dots[activeIndex]?.focus();
  });

  select(0);
})();

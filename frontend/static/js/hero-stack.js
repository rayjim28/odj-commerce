/* Progressive enhancement for the five overlapping product cards.
 * Clicking a rear card reveals it; clicking the front card opens its product page.
 * Dots, arrow keys and touch swipes provide manual navigation. */
(() => {
  "use strict";
  const stack = document.querySelector("[data-hero-stack]");
  if (!stack) return;

  const cards = [...stack.querySelectorAll("[data-hero-card]")];
  const dots = [...stack.querySelectorAll("[data-hero-dot]")];
  if (!cards.length) return;
  let activeIndex = 0;
  let gesture = null;
  let suppressClick = false;

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

  stack.addEventListener("pointerdown", (event) => {
    suppressClick = false;
    gesture = event.isPrimary !== false && cards.length > 1 && (event.pointerType === "touch" || event.pointerType === "pen")
      ? { x: event.clientX, y: event.clientY } : null;
  });
  stack.addEventListener("pointerup", (event) => {
    if (!gesture) return;
    const dx = event.clientX - gesture.x;
    const dy = event.clientY - gesture.y;
    gesture = null;
    if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy) * 1.3) return;
    select(activeIndex + (dx < 0 ? 1 : -1));
    suppressClick = true;
    event.preventDefault();
  });
  stack.addEventListener("pointercancel", () => { gesture = null; });
  stack.addEventListener("click", (event) => {
    if (!suppressClick) return;
    suppressClick = false;
    event.preventDefault();
    event.stopPropagation();
  }, true);

  stack.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    if (!stack.contains(document.activeElement)) return;
    suppressClick = false;
    event.preventDefault();
    select(activeIndex + (event.key === "ArrowRight" ? 1 : -1));
    dots[activeIndex]?.focus();
  });

  select(0);
})();

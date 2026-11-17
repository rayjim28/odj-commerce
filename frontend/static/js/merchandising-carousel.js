/* Native-scroll carousels: no UI library, no auto-advancing distractions.
   Featured products reflect the owner's published Featured selection.
   Collection rail grows horizontally as more curated categories are available. */
(() => {
  "use strict";
  const featured = document.querySelector("[data-featured-carousel]");
  if (featured) {
    const track = featured.querySelector("[data-featured-track]");
    const slides = [...featured.querySelectorAll("[data-featured-slide]")];
    const prev = featured.querySelector("[data-featured-prev]");
    const next = featured.querySelector("[data-featured-next]");
    const counter = featured.querySelector("[data-featured-count]");
    let active = 0;
    function position(index) {
      return Math.max(0, slides[index].offsetLeft - slides[0].offsetLeft);
    }
    function update() {
      if (!slides.length) return;
      let closest = 0;
      let diff = Infinity;
      slides.forEach((slide, i) => {
        const distance = Math.abs(position(i) - track.scrollLeft);
        if (distance < diff) { diff = distance; closest = i; }
      });
      active = closest;
      if (counter) counter.textContent = (active + 1) + " / " + slides.length;
      if (prev) prev.disabled = active === 0;
      if (next) next.disabled = active === slides.length - 1;
    }
    function go(delta) {
      if (!slides.length) return;
      active = Math.max(0, Math.min(slides.length - 1, active + delta));
      track.scrollTo({ left: position(active), behavior: "smooth" });
      if (counter) counter.textContent = (active + 1) + " / " + slides.length;
      if (prev) prev.disabled = active === 0;
      if (next) next.disabled = active === slides.length - 1;
    }
    prev?.addEventListener("click", () => go(-1));
    next?.addEventListener("click", () => go(1));
    track?.addEventListener("scroll", update, { passive: true });
    track?.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      go(event.key === "ArrowRight" ? 1 : -1);
    });
    if (slides.length) update();
  }

  const collections = document.querySelector("[data-collection-track]");
  if (collections) {
    const prev = document.querySelector("[data-collection-prev]");
    const next = document.querySelector("[data-collection-next]");
    function update() {
      const end = Math.max(0, collections.scrollWidth - collections.clientWidth);
      if (prev) prev.disabled = collections.scrollLeft <= 2;
      if (next) next.disabled = collections.scrollLeft >= end - 2;
    }
    function go(direction) {
      const card = collections.querySelector(".v71-collection-card");
      const amount = (card?.getBoundingClientRect().width || 245) + 15;
      collections.scrollBy({ left: direction * amount, behavior: "smooth" });
    }
    prev?.addEventListener("click", () => go(-1));
    next?.addEventListener("click", () => go(1));
    collections.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }
})();
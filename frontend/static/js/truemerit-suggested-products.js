(() => {
  'use strict';

  document.querySelectorAll('[data-recommendation-carousel]').forEach(section => {
    const track = section.querySelector('.tm-suggested-track');
    const controls = section.querySelector('.tm-suggested-controls');
    if (!track || !controls) return;

    const previous = controls.querySelector('.tm-suggested-prev');
    const next = controls.querySelector('.tm-suggested-next');

    function updateControls() {
      // No clipped cards or distracting arrows when the available items fit.
      const remaining = track.scrollWidth - track.clientWidth;
      controls.hidden = remaining <= 2;
      previous.disabled = track.scrollLeft <= 2;
      next.disabled = track.scrollLeft >= remaining - 2;
    }

    function cardStep() {
      const first = track.querySelector('.tm-suggested-card');
      if (!first) return 0;
      const gap = parseFloat(getComputedStyle(track).columnGap) || 18;
      return first.getBoundingClientRect().width + gap;
    }

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    function move(direction) {
      const step = cardStep();
      if (!step) return;
      track.scrollBy({
        left: direction * step,
        behavior: reducedMotion.matches ? 'auto' : 'smooth'
      });
    }

    previous.addEventListener('click', () => move(-1));
    next.addEventListener('click', () => move(1));
    track.addEventListener('scroll', updateControls, {passive: true});
    window.addEventListener('resize', updateControls);
    window.addEventListener('load', updateControls, {once: true});
    requestAnimationFrame(updateControls);
  });
})();

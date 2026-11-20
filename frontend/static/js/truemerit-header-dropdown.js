(() => {
  'use strict';

  document.querySelectorAll('.site-header').forEach(header => {
    const panel = header.querySelector('#tm-header-menu');
    const triggers = [...header.querySelectorAll('[data-tm-menu-trigger]')];
    if (!panel || !triggers.length) return;

    let lastTrigger = null;

    function setOpen(open, focusLink = false) {
      panel.hidden = !open;
      triggers.forEach(button => button.setAttribute('aria-expanded', String(open)));
      if (open) {
        const search = header.querySelector('#header-search');
        const searchButton = header.querySelector('#search-trigger');
        if (search) search.classList.remove('open');
        if (searchButton) searchButton.setAttribute('aria-expanded', 'false');
        if (focusLink) {
          const target = window.matchMedia('(max-width: 940px)').matches
            ? panel.querySelector('a')
            : panel.querySelector('a:not(.tm-header-menu-home)');
          target?.focus();
        }
      }
    }

    triggers.forEach(button => {
      button.addEventListener('click', () => {
        const willOpen = panel.hidden;
        lastTrigger = button;
        setOpen(willOpen, willOpen);
      });
    });

    panel.addEventListener('click', event => {
      const link = event.target.closest('a');
      if (!link) return;
      const category = link.dataset.tmNavCategory;
      if (category) {
        const filter = [...document.querySelectorAll('#filters [data-category]')]
          .find(item => item.dataset.category === category);
        if (filter) filter.click();
      }
      setOpen(false);
    });

    document.addEventListener('pointerdown', event => {
      if (panel.hidden) return;
      if (panel.contains(event.target) || triggers.some(b => b.contains(event.target))) return;
      setOpen(false);
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !panel.hidden) {
        setOpen(false);
        lastTrigger?.focus();
        event.preventDefault();
      }
    });

    const searchTrigger = header.querySelector('#search-trigger');
    searchTrigger?.addEventListener('click', () => setOpen(false));

    window.addEventListener('resize', () => setOpen(false));
  });
})();

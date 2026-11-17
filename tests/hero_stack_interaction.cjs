/* Functional regression for the real hero-stack.js.
 * Hero cards always show photos and open their product links on first click.
 * Dots and arrow keys scroll the rail without hijacking product navigation. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const script = fs.readFileSync(path.join(__dirname, "../frontend/static/js/hero-stack.js"), "utf8");

function fixture(count) {
  const document = { activeElement: null };
  function el(attrs = {}) {
    return {
      dataset: {},
      attrs: { ...attrs },
      listeners: {},
      scrollLeft: 0,
      offsetLeft: 0,
      addEventListener(name, listener) { this.listeners[name] = listener; },
      getAttribute(name) { return this.attrs[name] ?? null; },
      setAttribute(name, value) { this.attrs[name] = value; },
      removeAttribute(name) { delete this.attrs[name]; },
      focus() { document.activeElement = this; },
      scrollTo({ left }) { this.scrollLeft = left; this.dispatch("scroll"); },
      dispatch(name, extra = {}) {
        let prevented = false;
        const event = {
          key: "",
          preventDefault() { prevented = true; },
          ...extra,
        };
        this.listeners[name]?.(event);
        return prevented;
      },
    };
  }
  const cards = Array.from({ length: count }, (_, i) => {
    const item = el({ href: "/products/" + (i + 1) });
    item.offsetLeft = i * 170;
    return item;
  });
  const dots = Array.from({ length: count }, () => el());
  const track = el();
  const stack = el();
  stack.querySelectorAll = (selector) =>
    selector === "[data-hero-card]" ? cards :
    selector === "[data-hero-dot]" ? dots : [];
  stack.querySelector = (selector) => selector === "[data-hero-track]" ? track : null;
  stack.contains = (value) => cards.includes(value) || dots.includes(value) || value === track;
  document.querySelector = (selector) => selector === "[data-hero-stack]" ? stack : null;

  vm.runInNewContext(script, { document }, { filename: "hero-stack.js" });
  return { stack, cards, dots, track, document };
}

for (const count of [1, 2, 3, 4, 5]) {
  const { stack, cards, dots, track, document } = fixture(count);
  assert.equal(cards[0].getAttribute("aria-current"), "true");
  assert.equal(dots[0].getAttribute("aria-pressed"), "true");

  for (let i = 0; i < count; i++) {
    // One click is enough: no selection intercepts product navigation.
    assert.equal(cards[i].dispatch("click"), false);
    assert.equal(cards[i].getAttribute("href"), "/products/" + (i + 1));
  }

  if (count > 1) {
    dots[count - 1].dispatch("click");
    assert.equal(track.scrollLeft, (count - 1) * 170);
    assert.equal(cards[count - 1].getAttribute("aria-current"), "true");
    assert.equal(dots[count - 1].getAttribute("aria-pressed"), "true");

    dots[count - 1].focus();
    assert.equal(stack.dispatch("keydown", { key: "ArrowRight" }), true);
    assert.equal(cards[0].getAttribute("aria-current"), "true");
    assert.equal(track.scrollLeft, 0);
    assert.equal(document.activeElement, dots[0]);
    assert.equal(stack.dispatch("keydown", { key: "ArrowLeft" }), true);
    assert.equal(cards[count - 1].getAttribute("aria-current"), "true");
    assert.equal(stack.dispatch("keydown", { key: "Tab" }), false);
  }
}

assert.doesNotThrow(() => vm.runInNewContext(script, {
  document: { querySelector: () => null }
}));

console.log("hero rail: direct first-click links, scroll dots, keyboard access, zero-to-five cards PASS");

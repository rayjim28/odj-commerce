/* Functional regression for the real hero-stack.js (no DOM library needed). */
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const script = fs.readFileSync(
  path.join(__dirname, "../frontend/static/js/hero-stack.js"), "utf8"
);

function fixture(count) {
  const document = { activeElement: null };
  function el(attrs = {}) {
    return {
      dataset: {},
      attrs: { ...attrs },
      listeners: {},
      addEventListener(name, listener) { this.listeners[name] = listener; },
      getAttribute(name) { return this.attrs[name] ?? null; },
      setAttribute(name, value) { this.attrs[name] = value; },
      removeAttribute(name) { delete this.attrs[name]; },
      focus() { document.activeElement = this; },
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

  const cards = Array.from({ length: count }, (_, i) =>
    el({ href: "/products/" + (i + 1) })
  );
  const dots = Array.from({ length: count }, () => el());
  const stack = el();
  stack.querySelectorAll = (selector) =>
    selector === "[data-hero-card]" ? cards :
    selector === "[data-hero-dot]" ? dots : [];
  stack.contains = (value) => cards.includes(value) || dots.includes(value);
  document.querySelector = (selector) =>
    selector === "[data-hero-stack]" ? stack : null;

  vm.runInNewContext(script, { document }, { filename: "hero-stack.js" });
  return { stack, cards, dots, document };
}

for (const count of [1, 2, 3, 4, 5]) {
  const { stack, cards, dots, document } = fixture(count);
  assert.equal(cards[0].dataset.slot, "0");
  assert.equal(cards[0].getAttribute("aria-current"), "true");
  assert.equal(dots[0].getAttribute("aria-pressed"), "true");

  // Front card click must retain its real URL navigation.
  assert.equal(cards[0].dispatch("click"), false);
  assert.equal(cards[0].getAttribute("href"), "/products/1");

  if (count > 1) {
    // A visible rear card selects without navigating away.
    assert.equal(cards[1].dispatch("click"), true);
    assert.equal(cards[1].dataset.slot, "0");
    assert.equal(cards[1].getAttribute("aria-current"), "true");
    assert.equal(cards[0].getAttribute("aria-current"), null);
    assert.equal(dots[1].getAttribute("aria-pressed"), "true");

    // Clicking that foreground card should then navigate.
    assert.equal(cards[1].dispatch("click"), false);
    assert.equal(cards[1].getAttribute("href"), "/products/2");

    // Dots and keyboard arrows select the correct card and wrap.
    dots[count - 1].dispatch("click");
    assert.equal(cards[count - 1].dataset.slot, "0");
    dots[count - 1].focus();
    assert.equal(stack.dispatch("keydown", { key: "ArrowRight" }), true);
    assert.equal(cards[0].dataset.slot, "0");
    assert.equal(document.activeElement, dots[0]);
    assert.equal(stack.dispatch("keydown", { key: "ArrowLeft" }), true);
    assert.equal(cards[count - 1].dataset.slot, "0");

    // Ordinary keys must be left alone.
    assert.equal(stack.dispatch("keydown", { key: "Tab" }), false);
  }
}

// No catalog should not throw or create fake clickable product cards.
const emptyDocument = { querySelector: () => null };
assert.doesNotThrow(() => vm.runInNewContext(script, { document: emptyDocument }));

console.log("hero-stack: real card links, rear selection, dots, arrow keys, and 0-5 cards PASS");

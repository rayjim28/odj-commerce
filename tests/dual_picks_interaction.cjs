/* Run the real rail controller against scrollable DOM fixtures. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const script = fs.readFileSync(path.join(__dirname, "../frontend/static/js/truemerit-dual-picks.js"), "utf8");

function element(properties = {}) {
  return {
    listeners: {}, ...properties,
    addEventListener(type, callback) {
      (this.listeners[type] ||= []).push(callback);
    },
    emit(type, properties = {}) {
      const event = { target: this, preventDefault() { this.prevented = true; }, ...properties };
      for (const callback of this.listeners[type] || []) callback(event);
      return event;
    },
  };
}

function fixture(counts) {
  const window = element();
  const panels = counts.map((count, group) => {
    const cards = Array.from({ length: count }, (_, i) => ({
      offsetLeft: 7 + i * 376, dataset: { pickTitle: "Group " + group + " product " + i },
    }));
    const controls = { hidden: true };
    const previous = element({ disabled: false });
    const next = element({ disabled: false });
    const status = { textContent: "" };
    const rail = element({
      scrollLeft: 0, clientWidth: 360, scrollWidth: count * 360 + Math.max(0, count - 1) * 16,
      querySelectorAll: () => cards,
      scrollTo({ left }) {
        this.scrollLeft = Math.max(0, Math.min(left, this.scrollWidth - this.clientWidth));
        this.emit("scroll");
      },
    });
    return {
      cards, rail, controls, previous, next, status,
      querySelector(selector) {
        return {
          "[data-pick-rail]": rail, "[data-pick-controls]": controls,
          '[data-pick-step="-1"]': previous, '[data-pick-step="1"]': next,
          "[data-pick-status]": status,
        }[selector];
      },
    };
  });
  const root = { querySelectorAll: () => panels };
  vm.runInNewContext(script, {
    document: { getElementById: () => root }, window,
  }, { filename: "truemerit-dual-picks.js" });
  return { panels, window };
}

for (const count of [1, 2, 3, 4]) {
  const { panels: [panel] } = fixture([count]);
  const { rail, controls, previous, next, status } = panel;
  assert.equal(controls.hidden, count < 2);
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, count < 2);
  if (count === 1) continue;
  next.emit("click");
  assert.equal(rail.scrollLeft, 376);
  assert.equal(status.textContent, "Group 0 product 1");
  previous.emit("click");
  assert.equal(rail.scrollLeft, 0);
  assert.equal(rail.emit("keydown", { key: "End" }).prevented, true);
  assert.equal(next.disabled, true);
  assert.equal(rail.scrollLeft, (count - 1) * 376);
  next.emit("click");
  assert.equal(rail.scrollLeft, (count - 1) * 376);
  rail.emit("keydown", { key: "Home" });
  assert.equal(previous.disabled, true);
  rail.emit("keydown", { key: "ArrowRight" });
  assert.equal(rail.scrollLeft, 376);
  rail.emit("keydown", { key: "ArrowLeft" });
  assert.equal(rail.scrollLeft, 0);
  assert.equal(rail.emit("keydown", { key: "Tab" }).prevented, undefined);
  assert.equal(rail.emit("keydown", { key: "ArrowRight", target: {} }).prevented, undefined);
  assert.equal(rail.emit("keydown", { key: "ArrowRight", altKey: true }).prevented, undefined);
  // Native touch/trackpad scrolling updates navigation and the spoken product title.
  rail.scrollLeft = (count - 1) * 376;
  rail.emit("scroll");
  assert.equal(next.disabled, true);
  assert.equal(previous.disabled, false);
  assert.equal(status.textContent, "Group 0 product " + (count - 1));
}

{
  const { panels: [first, second], window } = fixture([3, 2]);
  second.next.emit("click");
  assert.equal(first.rail.scrollLeft, 0);
  assert.equal(second.rail.scrollLeft, 376);
  second.rail.clientWidth = second.rail.scrollWidth;
  window.emit("resize");
  assert.equal(second.controls.hidden, true);
  assert.equal(first.controls.hidden, false);
}
assert.doesNotThrow(() => fixture([0]));
assert.doesNotThrow(() => vm.runInNewContext(script, {
  document: { getElementById: () => null }, window: {},
}));
console.log("featured picks: buttons, keyboard, native scroll, boundaries, resize and independent groups PASS");

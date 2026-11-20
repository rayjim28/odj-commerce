/* Exercise the real collection controller at one-, two- and three-card widths. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const script = fs.readFileSync(path.join(__dirname, "../frontend/static/js/truemerit-routine-modern.js"), "utf8");
function element(properties = {}) {
  return {
    listeners: {}, ...properties,
    addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); },
    emit(type, properties = {}) {
      const event = { target: this, preventDefault() { this.prevented = true; }, ...properties };
      for (const callback of this.listeners[type] || []) callback(event);
      return event;
    },
  };
}
function fixture(count, width = 300, cardWidth = 300) {
  const window = element();
  const previous = element({ disabled: false });
  const next = element({ disabled: false });
  const status = { textContent: "" };
  const cards = Array.from({ length: count }, (_, i) => ({
    offsetLeft: 4 + i * (cardWidth + 20), dataset: { merchTitle: "Collection " + i },
  }));
  const track = element({
    clientWidth: width, scrollWidth: count * cardWidth + Math.max(0, count - 1) * 20,
    scrollLeft: 0, querySelectorAll: () => cards,
    scrollTo({ left }) {
      this.scrollLeft = Math.max(0, Math.min(left, Math.max(0, this.scrollWidth - this.clientWidth)));
      this.emit("scroll");
    },
  });
  const nav = { hidden: true, querySelector: selector => selector.includes('"-1"') ? previous : next };
  const section = { querySelector: selector => ({
    ".v71-collections-grid": track, ".tm-routine-nav": nav, "[data-routine-status]": status,
  })[selector] };
  vm.runInNewContext(script, { document: { querySelector: () => section }, window });
  return { window, track, nav, previous, next, status };
}
for (const count of [1, 2, 3]) {
  const { track, nav, previous, next, status } = fixture(count);
  assert.equal(nav.hidden, count === 1);
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, count === 1);
  if (count === 1) continue;
  next.emit("click");
  assert.equal(track.scrollLeft, 320);
  assert.equal(status.textContent, "Collection 1");
  assert.equal(track.emit("keydown", { key: "End" }).prevented, true);
  assert.equal(track.scrollLeft, (count - 1) * 320);
  assert.equal(next.disabled, true);
  track.emit("keydown", { key: "Home" });
  assert.equal(previous.disabled, true);
  track.emit("keydown", { key: "ArrowRight" });
  assert.equal(track.scrollLeft, 320);
  track.emit("keydown", { key: "ArrowLeft" });
  assert.equal(track.scrollLeft, 0);
  assert.equal(track.emit("keydown", { key: "Tab" }).prevented, undefined);
  assert.equal(track.emit("keydown", { key: "ArrowRight", altKey: true }).prevented, undefined);
  assert.equal(track.emit("keydown", { key: "ArrowRight", target: {} }).prevented, undefined);
  track.scrollLeft = (count - 1) * 320;
  track.emit("scroll");
  assert.equal(next.disabled, true);
}
{
  const { track, next, previous, nav, window } = fixture(3, 660, 320);
  assert.equal(nav.hidden, false);
  next.emit("click");
  assert.equal(track.scrollLeft, 340);
  assert.equal(next.disabled, true);
  previous.emit("click");
  assert.equal(track.scrollLeft, 0);
  track.clientWidth = 1000;
  window.emit("resize");
  assert.equal(nav.hidden, true);
}
assert.equal(fixture(3, 1000, 320).nav.hidden, true);
assert.doesNotThrow(() => fixture(0));
assert.doesNotThrow(() => vm.runInNewContext(script, { document: { querySelector: () => null } }));
console.log("routine: navigation, keyboard, native scroll, one/two/three visible cards and resize PASS");

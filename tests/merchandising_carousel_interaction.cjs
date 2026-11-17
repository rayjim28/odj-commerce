/* Test actual native-scroll featured and collection carousel controllers. */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const code = fs.readFileSync(path.join(__dirname, "../frontend/static/js/merchandising-carousel.js"), "utf8");

function element() {
  return {
    textContent: "", disabled: false, scrollLeft: 0,
    listeners: {}, offsetLeft: 0, clientWidth: 500, scrollWidth: 1100,
    addEventListener(key, fn) { this.listeners[key] = fn; },
    emit(key, options = {}) {
      let prevented = false;
      this.listeners[key]?.({ preventDefault() { prevented = true; }, ...options });
      return prevented;
    },
    scrollTo({ left }) { this.scrollLeft = left; this.emit("scroll"); },
    scrollBy({ left }) {
      this.scrollLeft = Math.max(0, Math.min(this.scrollWidth - this.clientWidth, this.scrollLeft + left));
      this.emit("scroll");
    },
    getBoundingClientRect() { return { width: 245 }; },
  };
}

const slides = [0,1,2,3].map(i => Object.assign(element(), { offsetLeft: i * 880 }));
const track = element();
const prev = element(), next = element(), counter = element();
const collection = element(), colPrev = element(), colNext = element();
collection.querySelector = selector => selector === ".v71-collection-card" ? element() : null;
const featured = {
  querySelector(selector) {
    return {
      "[data-featured-track]": track,
      "[data-featured-prev]": prev,
      "[data-featured-next]": next,
      "[data-featured-count]": counter
    }[selector] || null;
  },
  querySelectorAll(selector) { return selector === "[data-featured-slide]" ? slides : []; },
};
const document = {
  querySelector(selector) {
    return {
      "[data-featured-carousel]": featured,
      "[data-collection-track]": collection,
      "[data-collection-prev]": colPrev,
      "[data-collection-next]": colNext
    }[selector] || null;
  }
};
const window = { listeners: {}, addEventListener(key, fn) { this.listeners[key] = fn; } };
vm.runInNewContext(code, { document, window }, { filename: "merchandising-carousel.js" });

assert.equal(counter.textContent, "1 / 4");
assert.equal(prev.disabled, true);
next.emit("click");
assert.equal(counter.textContent, "2 / 4");
assert.equal(track.scrollLeft, 880);
next.emit("click");
next.emit("click");
assert.equal(counter.textContent, "4 / 4");
assert.equal(next.disabled, true);
prev.emit("click");
assert.equal(counter.textContent, "3 / 4");
assert.equal(track.emit("keydown", { key: "ArrowLeft" }), true);
assert.equal(counter.textContent, "2 / 4");
assert.equal(track.emit("keydown", { key: "Tab" }), false);
assert.equal(colPrev.disabled, true);
assert.equal(colNext.disabled, false);
colNext.emit("click");
assert.equal(collection.scrollLeft, 260);
assert.equal(colPrev.disabled, false);
colPrev.emit("click");
assert.equal(collection.scrollLeft, 0);
window.listeners.resize();
assert.equal(colPrev.disabled, true);

console.log("featured: all 4 slides, controls, keyboard, counter, and collection scroll PASS");

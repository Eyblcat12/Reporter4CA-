const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('../../apps/frontend/node_modules/jsdom');
const html = fs.readFileSync(path.join(__dirname, '../template-studio-b-design-review.html'), 'utf8');
test('design review preserves source B layout and scenario', () => {
  const dom = new JSDOM(html); const d = dom.window.document;
  assert.equal(d.querySelectorAll('main > aside').length, 2);
  assert.equal(d.querySelectorAll('.sections li').length, 10);
  assert.equal(d.querySelectorAll('.sections .done').length, 7);
  assert.match(d.querySelector('.selected').textContent, /Danh sách máy chủ/);
  assert.equal(d.querySelectorAll('.field-card').length, 3);
  assert.match(d.querySelector('.canvas').textContent, /REPORTER_INVENTORY_SERVER/);
  assert.equal(d.querySelectorAll('.lab, .paper, .doc-copy').length, 0);
  dom.window.close();
});
test('review has no remote dependencies, avatar, fake navigation or runtime calls', () => {
  const dom = new JSDOM(html); const d = dom.window.document;
  assert.equal(d.querySelectorAll('script[src],link[href],img,iframe,a[href="#"]').length,0);
  assert.equal(d.querySelectorAll('button').length,2);
  assert.match(d.querySelector('dialog').textContent,/chưa lưu mapping/);
  assert.doesNotMatch(d.querySelector('script').textContent,/fetch|XMLHttpRequest|localStorage/);
  assert.match(html,/prefers-reduced-motion/);
  dom.window.close();
});

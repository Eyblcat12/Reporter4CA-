const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('../../apps/frontend/node_modules/jsdom');
const html = fs.readFileSync(path.join(__dirname, '../template-studio-workspace-b.html'), 'utf8');
function open() {
  return new JSDOM(html, { runScripts: 'dangerously', beforeParse(w) {
    w.setTimeout = fn => { queueMicrotask(fn); return 1; };
  }});
}
test('initial outline, selection and theme are consistent', () => {
  const dom = open(); const d = dom.window.document;
  assert.equal(d.querySelectorAll('#outline button').length, 10);
  assert.equal(d.getElementById('count').textContent, '7/10 đã duyệt');
  assert.equal(d.querySelector('[aria-current=true]').dataset.section, '2');
  d.getElementById('theme').click();
  assert.ok(d.body.classList.contains('dark'));
  dom.window.close();
});
test('field edits retain keyboard focus and draft across sections', () => {
  const dom=open(); const w=dom.window; const d=w.document;
  const field=d.querySelector('[aria-label="Cột đích cho hostname"]');field.focus();field.value='1';field.dispatchEvent(new w.Event('change'));
  assert.equal(d.activeElement.getAttribute('aria-label'),'Cột đích cho hostname');
  w.selectSection(3);w.selectSection(2);
  assert.equal(d.querySelector('[aria-label="Cột đích cho hostname"]').value,'1');
  assert.match(d.getElementById('revision').textContent,/Bản nháp/);
  dom.window.close();
});
test('timeout recovery survives section switch and locks uncertain mapping', async () => {
  const dom=open();const w=dom.window;const d=w.document;
  d.getElementById('scenario').value='unknown';await w.save();
  assert.ok(d.getElementById('anchor').disabled);
  w.selectSection(3);w.selectSection(2);
  assert.match(d.getElementById('issue').textContent,/Chưa rõ/);
  assert.ok(d.getElementById('approve').disabled);
  d.querySelector('#issue button').click();
  assert.equal(d.getElementById('count').textContent,'8/10 đã duyệt');
  assert.equal(d.getElementById('issue').textContent,'');
  dom.window.close();
});
test('success is acknowledged once and advances to missing mapping', async () => {
  const dom=open();const w=dom.window;const d=w.document;
  const saving=w.save();await w.save();await saving;
  assert.equal(d.getElementById('count').textContent,'8/10 đã duyệt');
  assert.match(d.getElementById('revision').textContent,/rev\. 13/);
  assert.equal(d.getElementById('inspectorTitle').textContent,'IoC');
  assert.ok(d.getElementById('approve').disabled);
  dom.window.close();
});
test('conflict does not approve and recovery requires explicit review', async () => {
  const dom=open();const w=dom.window;const d=w.document;
  d.getElementById('scenario').value='conflict';await w.save();
  assert.equal(d.getElementById('count').textContent,'7/10 đã duyệt');
  w.selectSection(1);w.selectSection(2);
  assert.match(d.getElementById('issue').textContent,/revision mới/);
  d.querySelector('#issue button').click();
  assert.equal(d.getElementById('count').textContent,'7/10 đã duyệt');
  assert.equal(d.getElementById('approve').disabled,false);
  dom.window.close();
});
test('duplicate target columns block approval', async () => {
  const dom=open();const w=dom.window;const d=w.document;
  const field=d.querySelector('[aria-label="Cột đích cho hostname"]');
  field.value='1';field.dispatchEvent(new w.Event('change'));await w.save();
  assert.match(d.getElementById('message').textContent,/cột bị trùng/);
  assert.equal(d.getElementById('count').textContent,'7/10 đã duyệt');
  dom.window.close();
});

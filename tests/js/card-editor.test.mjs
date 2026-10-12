// Loads the real card-editor.js into jsdom and drives it the way Home
// Assistant does: setConfig on every edit, hass on every state change.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const source = readFileSync(
  new URL('../../www/community/medication-card/card-editor.js', import.meta.url),
  'utf8',
);

function makeEditor(config) {
  const dom = new JSDOM('<!doctype html><body></body>', { runScripts: 'outside-only' });
  dom.window.eval(source);
  const editor = dom.window.document.createElement('medication-card-editor');
  dom.window.document.body.appendChild(editor);
  editor.setConfig(config);
  editor.hass = {};
  return editor;
}

test('a title with quotes and markup lands intact in the title input', () => {
  const title = `Mom's "AM" meds <b>&amp;</b>`;
  const editor = makeEditor({ title, entities: [] });

  const input = editor.querySelector('#med-card-title');
  assert.equal(input.value, title);
  assert.equal(input.getAttribute('placeholder'), 'Medications');
  assert.equal(editor.querySelectorAll('b').length, 0);
});

test('a later setConfig updates the title input', () => {
  const editor = makeEditor({ title: 'Morning', entities: [] });
  editor.setConfig({ title: 'Evening "PM"', entities: [] });
  assert.equal(editor.querySelector('#med-card-title').value, 'Evening "PM"');
});

test('hass updates and setConfig echoes keep the entity input that has focus', () => {
  const editor = makeEditor({ entities: ['sensor.medication_aspirin'] });
  const input = editor.querySelector('#med-entity-0');

  editor.hass = {};
  editor.setConfig({ entities: ['sensor.medication_aspirin_81'] });

  assert.equal(editor.querySelector('#med-entity-0'), input);
  assert.equal(input.value, 'sensor.medication_aspirin_81');
  assert.equal(
    editor.querySelector('.remove-btn').getAttribute('aria-label'),
    'Remove entity sensor.medication_aspirin_81',
  );
});

test('adding and removing entities still rebuilds the rows', () => {
  const editor = makeEditor({ entities: ['sensor.medication_a', 'sensor.medication_b'] });
  const changes = [];
  editor.addEventListener('config-changed', (e) => changes.push(e.detail.config));

  editor.querySelector('#add-btn').click();
  assert.equal(editor.querySelectorAll('.entity-row').length, 3);

  editor.querySelectorAll('.remove-btn')[0].click();
  const values = [...editor.querySelectorAll('.entity-row input')].map((i) => i.value);
  assert.deepEqual(values, ['sensor.medication_b', '']);
  assert.deepEqual(changes.at(-1).entities, ['sensor.medication_b', '']);
});

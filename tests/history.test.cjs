const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function history() {
  const context = vm.createContext({Date});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/history.js'), 'utf8'), context);
  return new context.historyView.Months();
}
const stamp = (year, month, day, hour=12) => new Date(year, month - 1, day, hour).getTime() / 1000;
test('opens the current month and keeps earlier months separate without truncating entries', () => {
  const model = history();
  const rows = Array.from({length:75}, (_,i) => ({id:i+1,created:stamp(2026,10,26)-i}));
  rows.push({id:76,created:stamp(2026,9,30)});
  model.update(rows, 'created', new Date(2026,9,26));
  assert.equal(model.selected, '2026-10');
  assert.equal(model.groups.get('2026-10').length, 75);
  assert.equal(model.groups.get('2026-09').length, 1);
  assert.equal(model.groups.get('2026-10')[0].id, 1);
});
test('archived selection survives refresh and new month resets to its empty current section', () => {
  const model = history();
  const rows = [{id:1,created:stamp(2026,10,26)}, {id:2,created:stamp(2026,9,30)}];
  model.update(rows, 'created', new Date(2026,9,31,23,59));
  model.select('2026-09');
  model.update(rows, 'created', new Date(2026,9,31,23,59,30));
  assert.equal(model.selected, '2026-09');
  model.update(rows, 'created', new Date(2026,10,1,0,0));
  assert.equal(model.selected, '2026-11');
  assert.equal(model.groups.get('2026-11').length, 0);
  assert.deepEqual(Array.from(model.groups.keys()), ['2026-11','2026-10','2026-09']);
});
test('expired selected months return to current, and delivery timestamps use the same model', () => {
  const model = history();
  model.update([{id:1,created:stamp(2026,9,1)}], 'created', new Date(2026,9,1));
  model.select('2026-09');
  model.update([{id:2,created:stamp(2026,10,2)}], 'created', new Date(2026,9,2));
  assert.equal(model.selected, '2026-10');
  model.select('not-a-month');
  assert.equal(model.selected, '2026-10');
});
test('month grouping follows local displayed dates at a boundary rather than UTC month strings', () => {
  const model = history();
  const lastLocalOctober = new Date(2026,9,31,23,59,59);
  model.update([{id:1,created_at:lastLocalOctober.getTime()/1000}], 'created_at', lastLocalOctober);
  assert.equal(model.groups.get('2026-10').length, 1);
  model.update([{id:1,created_at:lastLocalOctober.getTime()/1000}], 'created_at', new Date(2026,10,1));
  assert.equal(model.selected, '2026-11');
  assert.equal(model.groups.get('2026-10').length, 1);
});

test('current month toggles between latest two notifications and complete history', () => {
  const model = history();
  const rows = Array.from({length:12}, (_,i) => ({id:i,created:stamp(2026,10,26)-i}));
  model.update(rows, 'created', new Date(2026,9,26));
  assert.equal(model.expanded, false);
  assert.equal(model.visibleEntries(2).length, 2);
  model.select('2026-10');
  assert.equal(model.expanded, true);
  assert.equal(model.visibleEntries(2).length, 12);
  model.update(rows, 'created', new Date(2026,9,27));
  assert.equal(model.expanded, true);
  model.select('2026-10');
  assert.equal(model.expanded, false);
  assert.equal(model.visibleEntries(2).length, 2);
});
test('delivery preview contains one attempt; archived months toggle and rollover starts compact', () => {
  const model = history();
  const rows = [{id:1,created:stamp(2026,10,26)}, {id:2,created:stamp(2026,10,25)}, {id:3,created:stamp(2026,9,30)}];
  model.update(rows, 'created', new Date(2026,9,26));
  assert.equal(model.visibleEntries(1).length, 1);
  model.select('2026-09');
  assert.equal(model.expanded, true);
  model.select('2026-09');
  assert.equal(model.expanded, false);
  model.update(rows, 'created', new Date(2026,10,1));
  assert.equal(model.selected, '2026-11');
  assert.equal(model.expanded, false);
  assert.equal(model.visibleEntries(1).length, 0);
});

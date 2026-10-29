import test from 'node:test';
import assert from 'node:assert/strict';
import { escapeCsvCell, rowsToCsv } from '../src/csv.js';

test('CSV escaping neutralizes spreadsheet formulas and preserves quoted text', () => {
  assert.equal(escapeCsvCell('=1+1'), `"'=1+1"`);
  assert.equal(escapeCsvCell('  @SUM(A1:A2)'), `"'  @SUM(A1:A2)"`);
  assert.equal(escapeCsvCell('Fund "A"'), `"Fund ""A"""`);
});

test('CSV export keeps header order and escapes untrusted cells', () => {
  assert.equal(rowsToCsv([{ name: '=cmd', country: 'US' }], ['name', 'country']), 'name,country\n"\'=cmd","US"');
});

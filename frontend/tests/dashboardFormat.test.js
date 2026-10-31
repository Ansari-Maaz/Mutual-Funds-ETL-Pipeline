import test from 'node:test';
import assert from 'node:assert/strict';
import { displayRunId, displayText, fmt, statusClass, statusLabel } from '../src/dashboardFormat.js';

test('dashboard formatting handles missing values and run identifiers', () => {
  assert.equal(fmt(183169), '183,169');
  assert.equal(displayRunId('python-277'), 'python-277');
  assert.equal(displayRunId('abcdefghijk'), 'abcdefgh');
  assert.equal(displayRunId(null), '');
});

test('displayText handles nested source values without rendering objects as generic text', () => {
  assert.equal(displayText({ name: 'United States' }), 'United States');
  assert.equal(displayText(['US', { label: 'Dollar' }]), 'US, Dollar');
  assert.equal(displayText(null, 'Unavailable'), 'Unavailable');
});

test('status labels and classes cover success, failure, in-progress, and unknown states', () => {
  assert.equal(statusLabel('partially_succeeded'), 'partially succeeded');
  assert.equal(statusClass('succeeded'), 'good');
  assert.equal(statusClass('unavailable'), 'bad');
  assert.equal(statusClass('queued'), 'working');
  assert.equal(statusClass('not_checked'), 'neutral');
});

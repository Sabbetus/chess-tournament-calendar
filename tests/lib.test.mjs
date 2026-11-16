// Unit tests for the small shared helpers. Run with `npm test` (Node 22.18+,
// which runs .ts files directly; no test framework needed).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { durationDays, formatDateRange, formatDuration } from '../src/lib/dates.ts';
import { retentionCutoff, isRetained, PAGE_RETENTION_DAYS } from '../src/lib/retention.js';
import { isDelisted, MAX_CONSECUTIVE_MISSES } from '../src/lib/tournamentStatus.js';

test('durationDays is inclusive and never below 1', () => {
  assert.equal(durationDays('2026-11-17', '2026-11-17'), 1);
  assert.equal(durationDays('2026-11-17', '2026-11-22'), 6);
  // A source listing an end date before the start must not give 0 or negative.
  assert.equal(durationDays('2026-11-22', '2026-10-05'), 1);
});

test('formatDateRange shows a single date for one-day or impossible ranges', () => {
  assert.equal(formatDateRange('2026-11-17', '2026-11-17', 'en-GB'), '17 Nov 2026');
  assert.equal(formatDateRange('2026-11-22', '2026-10-05', 'en-GB'), '22 Nov 2026');
  assert.equal(formatDateRange('2026-11-17', '2026-11-22', 'en-GB'), '17 Nov – 22 Nov 2026');
});

test('formatDuration pluralises', () => {
  assert.equal(formatDuration(1, 'day', 'days'), '1 day');
  assert.equal(formatDuration(6, 'day', 'days'), '6 days');
});

test('retention cutoff is PAGE_RETENTION_DAYS before the data refresh', () => {
  assert.equal(PAGE_RETENTION_DAYS, 60);
  assert.equal(retentionCutoff('2026-11-16T10:00:00Z'), '2026-09-17');
  assert.equal(isRetained({ startDate: '2026-09-17' }, '2026-09-17'), true);
  assert.equal(isRetained({ startDate: '2026-09-16' }, '2026-09-17'), false);
});

test('isDelisted needs an upcoming tournament that missed enough scrapes', () => {
  const up = (n) => ({ status: 'upcoming', consecutiveMisses: n });
  assert.equal(isDelisted(up(MAX_CONSECUTIVE_MISSES - 1)), false);
  assert.equal(isDelisted(up(MAX_CONSECUTIVE_MISSES)), true);
  assert.equal(isDelisted({ status: 'upcoming' }), false);
  assert.equal(isDelisted({ status: 'concluded', consecutiveMisses: 99 }), false);
});

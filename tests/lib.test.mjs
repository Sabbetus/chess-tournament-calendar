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

import { countrySummary } from '../src/lib/countrySummary.ts';

test('country summary reads as a sentence in every language', () => {
  assert.equal(countrySummary('en', 'Finland', 4, 2), 'Finland has 6 upcoming chess tournaments: 4 classical and 2 rapid.');
  assert.equal(countrySummary('en', 'Fiji', 0, 1), 'Fiji has 1 upcoming chess tournament, and it is rapid.');
  assert.equal(countrySummary('en', 'Peru', 3, 0), 'Peru has 3 upcoming chess tournaments, all classical.');
  assert.equal(countrySummary('fi', 'Suomi', 4, 2), 'Maassa Suomi on tulossa 6 shakkiturnausta: 4 klassista ja 2 nopeaa.');
  assert.equal(countrySummary('fi', 'Suomi', 1, 1), 'Maassa Suomi on tulossa 2 shakkiturnausta: 1 klassinen ja 1 nopea.');
  assert.equal(countrySummary('es', 'España', 1, 5), 'En España hay 6 torneos de ajedrez próximos: 1 clásico y 5 rápidos.');
  assert.equal(countrySummary('de', 'Deutschland', 22, 4), 'In Deutschland stehen 26 Schachturniere an, davon 22 mit klassischer und 4 mit Schnellschach-Bedenkzeit.');
  for (const l of ['en', 'es', 'pt', 'de', 'cs', 'fi']) {
    assert.equal(countrySummary(l, 'X', 0, 0), '');
    assert.match(countrySummary(l, 'X', 2, 0), /X/);
    assert.match(countrySummary(l, 'X', 0, 1), /X/);
  }
});

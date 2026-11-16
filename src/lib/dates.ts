const DAY_MS = 24 * 60 * 60 * 1000;

// Inclusive length in days, never below 1: a source occasionally lists an end
// date before the start date, and that must not show as a zero or negative
// duration.
export function durationDays(start: string, end: string): number {
  const s = new Date(start + 'T00:00:00');
  const e = new Date(end + 'T00:00:00');
  return Math.max(1, Math.round((e.getTime() - s.getTime()) / DAY_MS) + 1);
}

// "15 Nov – 17 Nov 2026", or just "15 Nov 2026" for a one-day event.
export function formatDateRange(start: string, end: string, locale: string): string {
  const withYear = { day: 'numeric', month: 'short', year: 'numeric' } as const;
  const s = new Date(start + 'T00:00:00');
  // One-day event, or an end date that isn't after the start: show the start.
  if (end <= start) return s.toLocaleDateString(locale, withYear);
  const e = new Date(end + 'T00:00:00');
  return `${s.toLocaleDateString(locale, { day: 'numeric', month: 'short' })} – ${e.toLocaleDateString(locale, withYear)}`;
}

// The same without the year, for compact lists.
export function formatShortRange(start: string, end: string, locale: string): string {
  const s = new Date(start + 'T00:00:00').toLocaleDateString(locale, { day: 'numeric', month: 'short' });
  if (end <= start) return s;
  const e = new Date(end + 'T00:00:00').toLocaleDateString(locale, { day: 'numeric', month: 'short' });
  return `${s} – ${e}`;
}

export function formatDuration(days: number, dayLabel: string, daysLabel: string): string {
  return `${days} ${days === 1 ? dayLabel : daysLabel}`;
}

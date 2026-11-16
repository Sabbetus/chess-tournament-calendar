// Tournaments that started more than this many days before the data's last
// refresh no longer get a page. They've been noindex since the day they
// started, so by now they are out of search results; keeping all of them made
// the built site grow by ~350 MB a month. The archive still holds every
// tournament, so raising this brings the pages back on the next deploy.
export const PAGE_RETENTION_DAYS = 60;

// Anchored to the data's own refresh time (meta.json) rather than the wall
// clock, so every module in one build agrees on the cutoff.
export function retentionCutoff(lastUpdatedIso) {
  const d = new Date(lastUpdatedIso);
  d.setUTCDate(d.getUTCDate() - PAGE_RETENTION_DAYS);
  return d.toISOString().slice(0, 10);
}

export function isRetained(tournament, cutoff) {
  return tournament.startDate >= cutoff;
}

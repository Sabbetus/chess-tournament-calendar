// "Similar tournaments" for a given tournament is purely a function of
// archive data (id, status, name, country, countryCode, startDate, endDate)
// -- nothing about it depends on locale. The en and [lang] tournament pages
// both need it, so it's computed once per tournament id and memoized here
// rather than redone independently for all 6 locale renders of every page,
// which was multiplying an already-O(n) computation by 6x for no reason.

const CONTINENT: Record<string, string> = {
  FI:'EU',SE:'EU',NO:'EU',DK:'EU',IS:'EU',GB:'EU',IE:'EU',FR:'EU',ES:'EU',PT:'EU',
  DE:'EU',AT:'EU',CH:'EU',NL:'EU',BE:'EU',LU:'EU',IT:'EU',GR:'EU',CY:'EU',MT:'EU',
  PL:'EU',CZ:'EU',SK:'EU',HU:'EU',RO:'EU',BG:'EU',RS:'EU',HR:'EU',SI:'EU',BA:'EU',
  ME:'EU',MK:'EU',AL:'EU',XK:'EU',LT:'EU',LV:'EU',EE:'EU',BY:'EU',UA:'EU',MD:'EU',
  RU:'EU',GE:'AS',AM:'AS',AZ:'AS',TR:'AS',
  IN:'AS',CN:'AS',JP:'AS',KR:'AS',TH:'AS',VN:'AS',PH:'AS',ID:'AS',MY:'AS',SG:'AS',
  PK:'AS',BD:'AS',LK:'AS',NP:'AS',MN:'AS',UZ:'AS',KZ:'AS',KG:'AS',TM:'AS',
  AE:'AS',QA:'AS',KW:'AS',SA:'AS',IR:'AS',IQ:'AS',JO:'AS',LB:'AS',SY:'AS',IL:'AS',
  HK:'AS',
  US:'NA',CA:'NA',MX:'NA',GT:'NA',CR:'NA',CU:'NA',DO:'NA',PA:'NA',PR:'NA',
  BR:'SA',AR:'SA',CL:'SA',CO:'SA',PE:'SA',VE:'SA',UY:'SA',EC:'SA',
  AU:'OC',NZ:'OC',
  ZA:'AF',EG:'AF',MA:'AF',TN:'AF',DZ:'AF',KE:'AF',BW:'AF',ZM:'AF',CI:'AF',CV:'AF',
};

function getContinent(countryCode: string | null): string {
  return (countryCode && CONTINENT[countryCode]) || 'XX';
}

function durationDays(start: string, end: string): number {
  const s = new Date(start + 'T00:00:00');
  const e = new Date(end + 'T00:00:00');
  return Math.round((e.getTime() - s.getTime()) / (1000 * 60 * 60 * 24)) + 1;
}

function meaningfulWords(name: string): string[] {
  return name.toLowerCase().split(/\s+/).filter((w) => w.length > 1 && w !== '--');
}

function isSameFamily(a: string, b: string): boolean {
  const wa = meaningfulWords(a);
  const wb = meaningfulWords(b);
  const prefixLen = Math.min(3, wa.length, wb.length);
  if (wa.slice(0, prefixLen).join(' ') === wb.slice(0, prefixLen).join(' ')) return true;
  const setA = new Set(wa);
  const setB = new Set(wb);
  const intersection = [...setA].filter((w) => setB.has(w)).length;
  const union = new Set([...setA, ...setB]).size;
  return intersection / union > 0.6;
}

function scoreSimilar(candidate: any, target: any): number {
  if (candidate.id === target.id) return -1;
  if (candidate.status === 'concluded') return -1;
  if (isSameFamily(candidate.name, target.name)) return -1;

  const tDays = durationDays(target.startDate, target.endDate);
  const cDays = durationDays(candidate.startDate, candidate.endDate);
  if (Math.abs(tDays - cDays) > 3) return -1;

  let score = 0;
  const tStart = new Date(target.startDate + 'T00:00:00').getTime();
  const cStart = new Date(candidate.startDate + 'T00:00:00').getTime();
  const daysDiff = Math.abs((cStart - tStart) / (1000 * 60 * 60 * 24));
  score += Math.max(0, 14 - daysDiff) / 14 * 45;
  if (candidate.country === target.country) score += 25;
  const sameContinent = getContinent(candidate.countryCode) === getContinent(target.countryCode);
  if (!sameContinent) score -= 30;
  score += Math.max(0, 3 - Math.abs(tDays - cDays)) * 3;
  return score;
}

// Keyed by tournament id, not by (id, locale) -- the result is identical
// across locales, only the display labels built from it differ per page.
const cache = new Map<string, any[]>();

export function getSimilarTournaments(t: any, all: any[]): any[] {
  const cached = cache.get(t.id);
  if (cached) return cached;

  const upcoming = all.filter((x: any) => x.status === 'upcoming' && x.id !== t.id);
  const scored = upcoming
    .map((x: any) => ({ t: x, score: scoreSimilar(x, t) }))
    .filter(({ score }) => score >= 10)
    .sort((a: any, b: any) => b.score - a.score);

  const similar: any[] = [];
  for (const { t: candidate } of scored) {
    if (similar.length >= 5) break;
    const tooSimilarToSelected = similar.some((s: any) => isSameFamily(candidate.name, s.name));
    if (!tooSimilarToSelected) similar.push(candidate);
  }

  const result = similar.length > 0
    ? similar
    : upcoming.sort((a: any, b: any) => a.startDate.localeCompare(b.startDate)).slice(0, 5);

  cache.set(t.id, result);
  return result;
}

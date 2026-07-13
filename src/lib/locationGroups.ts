import { getContinent } from './continents.ts';
import { slugifyLocation, CONTINENT_SLUGS } from './locationSlug.ts';
import { countryName } from '../i18n/index.ts';

export interface CountryGroup {
  slug: string;
  englishName: string;
  displayName: string;
  countryCode: string | null;
  continentCode: string;
  items: any[];
}

export interface ContinentGroup {
  code: string;
  slug: string;
  items: any[];
  countries: { slug: string; displayName: string; count: number }[];
}

// Groups tournaments (upcoming + featured) by their country's display name.
// A country name can map to more than one raw entry if data is inconsistent,
// so entries are merged by slug rather than by the raw name string. Entries
// with no ISO country code (regional bodies like "ASEAN" or "Asian Chess
// Fed.", shown in the main filter dropdown without a flag) have no real
// location, so they don't get a location hub page.
export function getCountryGroups(allItems: any[], lang: string): CountryGroup[] {
  const bySlug = new Map<string, CountryGroup>();
  for (const item of allItems) {
    if (!item.country || !item.countryCode) continue;
    const slug = slugifyLocation(item.country);
    if (!slug) continue;
    let group = bySlug.get(slug);
    if (!group) {
      group = {
        slug,
        englishName: item.country,
        displayName: countryName(item.country, item.countryCode, lang),
        countryCode: item.countryCode || null,
        continentCode: getContinent(item.countryCode),
        items: [],
      };
      bySlug.set(slug, group);
    }
    group.items.push(item);
  }
  return [...bySlug.values()].sort((a, b) => b.items.length - a.items.length);
}

export function getContinentGroups(allItems: any[], lang: string): ContinentGroup[] {
  const countryGroups = getCountryGroups(allItems, lang);
  const byCode = new Map<string, ContinentGroup>();
  for (const [code, slug] of Object.entries(CONTINENT_SLUGS)) {
    byCode.set(code, { code, slug, items: [], countries: [] });
  }
  for (const cg of countryGroups) {
    const continent = byCode.get(cg.continentCode);
    if (!continent) continue; // 'XX' (unmapped country codes) has no continent page
    continent.items.push(...cg.items);
    continent.countries.push({ slug: cg.slug, displayName: cg.displayName, count: cg.items.length });
  }
  for (const continent of byCode.values()) {
    continent.countries.sort((a, b) => b.count - a.count);
  }
  return [...byCode.values()].filter((c) => c.items.length > 0);
}

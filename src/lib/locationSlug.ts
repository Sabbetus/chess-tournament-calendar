// Slugifies a country display name (e.g. "Bosnia & Herzegovina" -> "bosnia-herzegovina",
// "Côte d'Ivoire" -> "cote-d-ivoire") for use in /country/[slug]/ URLs.
export function slugifyLocation(name: string): string {
  return name
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '') // strip accents
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export const CONTINENT_SLUGS: Record<string, string> = {
  EU: 'europe', AS: 'asia', NA: 'north-america',
  SA: 'south-america', AF: 'africa', OC: 'oceania',
};

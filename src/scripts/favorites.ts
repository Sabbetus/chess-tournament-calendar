const KEY = 'ctc-favorite-countries';
export const FAVORITES_CHANGED_EVENT = 'ctc:favorites-changed';

export function getFavorites(): string[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]');
  } catch {
    return [];
  }
}

export function isFavorite(slug: string): boolean {
  return getFavorites().includes(slug);
}

// Returns the new favorited state (true = now favorited).
export function toggleFavorite(slug: string): boolean {
  const favs = getFavorites();
  const i = favs.indexOf(slug);
  const nowFavorited = i === -1;
  if (nowFavorited) favs.push(slug);
  else favs.splice(i, 1);
  try {
    localStorage.setItem(KEY, JSON.stringify(favs));
  } catch {
    // localStorage unavailable (private mode, quota) -- favoriting silently no-ops
  }
  window.dispatchEvent(new CustomEvent(FAVORITES_CHANGED_EVENT));
  return nowFavorited;
}

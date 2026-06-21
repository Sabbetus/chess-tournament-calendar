import en from './en.json';
import es from './es.json';
import pt from './pt.json';
import de from './de.json';
import cs from './cs.json';
import fi from './fi.json';

export const SUPPORTED_LANGS = ['en', 'es', 'pt', 'de', 'cs', 'fi'] as const;
export type Lang = typeof SUPPORTED_LANGS[number];

const translations: Record<string, Record<string, any>> = { en, es, pt, de, cs, fi };

export function getTranslations(lang: string): Record<string, any> {
  return translations[lang] ?? translations.en;
}

// Maps browser language codes to our supported langs
export const BROWSER_LANG_MAP: Record<string, Lang> = {
  es: 'es', pt: 'pt', de: 'de', cs: 'cs', sk: 'cs', fi: 'fi',
};

export function langPrefix(lang: string): string {
  return lang === 'en' ? '' : `/${lang}`;
}

export function langUrl(lang: string, currentPath: string): string {
  if (lang === 'en') return currentPath ? `/${currentPath}` : '/';
  return currentPath ? `/${lang}/${currentPath}` : `/${lang}/`;
}

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
  if (lang === 'en') return currentPath ? `/${currentPath}/` : '/';
  return currentPath ? `/${lang}/${currentPath}/` : `/${lang}/`;
}

// Overrides for entries that Intl.DisplayNames can't localize correctly:
// chess-specific sub-national teams (England/Scotland/Wales share code GB,
// Catalonia shares ES) and entries with no/ambiguous ISO code.
const COUNTRY_NAME_OVERRIDES: Record<string, Record<string, string>> = {
  es: {
    England: 'Inglaterra', Scotland: 'Escocia', Wales: 'Gales', Catalonia: 'Cataluña',
    Unknown: 'Desconocido', 'Trinidad and Tobago': 'Trinidad y Tobago', 'Hong Kong': 'Hong Kong',
  },
  pt: {
    England: 'Inglaterra', Scotland: 'Escócia', Wales: 'País de Gales', Catalonia: 'Catalunha',
    Unknown: 'Desconhecido', 'Trinidad and Tobago': 'Trinidad e Tobago', 'Hong Kong': 'Hong Kong',
  },
  de: {
    England: 'England', Scotland: 'Schottland', Wales: 'Wales', Catalonia: 'Katalonien',
    Unknown: 'Unbekannt', 'Trinidad and Tobago': 'Trinidad und Tobago', 'Hong Kong': 'Hongkong',
    Palestine: 'Palästina',
  },
  cs: {
    England: 'Anglie', Scotland: 'Skotsko', Wales: 'Wales', Catalonia: 'Katalánsko',
    Unknown: 'Neznámé', 'Trinidad and Tobago': 'Trinidad a Tobago', 'Hong Kong': 'Hongkong',
  },
  fi: {
    England: 'Englanti', Scotland: 'Skotlanti', Wales: 'Wales', Catalonia: 'Katalonia',
    Unknown: 'Tuntematon', 'Trinidad and Tobago': 'Trinidad ja Tobago', 'Hong Kong': 'Hongkong',
  },
};

const displayNamesCache: Record<string, Intl.DisplayNames> = {};

// Localize a country for the given language. `englishName` is the value used
// for filtering (kept as-is); the returned string is for display only.
export function countryName(englishName: string, code: string | null | undefined, lang: string): string {
  if (lang === 'en') return englishName;
  const override = COUNTRY_NAME_OVERRIDES[lang]?.[englishName];
  if (override) return override;
  if (code) {
    try {
      const dn = displayNamesCache[lang] ??=
        new Intl.DisplayNames([lang], { type: 'region' });
      const localized = dn.of(code);
      if (localized && localized !== code) return localized;
    } catch { /* fall through to English */ }
  }
  return englishName;
}

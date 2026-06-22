// Single source of truth for the country-code → continent mapping used by both
// the server-rendered pages and the client-side tournament list script.
export const CONTINENT_MAP: Record<string, string> = {
  FI:'EU',SE:'EU',NO:'EU',DK:'EU',IS:'EU',GB:'EU',IE:'EU',FR:'EU',ES:'EU',PT:'EU',
  DE:'EU',AT:'EU',CH:'EU',NL:'EU',BE:'EU',LU:'EU',IT:'EU',GR:'EU',CY:'EU',MT:'EU',
  PL:'EU',CZ:'EU',SK:'EU',HU:'EU',RO:'EU',BG:'EU',RS:'EU',HR:'EU',SI:'EU',BA:'EU',
  ME:'EU',MK:'EU',AL:'EU',XK:'EU',LT:'EU',LV:'EU',EE:'EU',BY:'EU',UA:'EU',MD:'EU',
  RU:'EU',GE:'AS',AM:'AS',AZ:'AS',TR:'AS',
  IN:'AS',CN:'AS',JP:'AS',KR:'AS',TH:'AS',VN:'AS',PH:'AS',ID:'AS',MY:'AS',SG:'AS',
  PK:'AS',BD:'AS',LK:'AS',NP:'AS',MN:'AS',UZ:'AS',KZ:'AS',KG:'AS',TM:'AS',
  AE:'AS',QA:'AS',KW:'AS',SA:'AS',IR:'AS',IQ:'AS',JO:'AS',LB:'AS',SY:'AS',IL:'AS',HK:'AS',
  US:'NA',CA:'NA',MX:'NA',GT:'NA',CR:'NA',CU:'NA',DO:'NA',PA:'NA',PR:'NA',
  BR:'SA',AR:'SA',CL:'SA',CO:'SA',PE:'SA',VE:'SA',UY:'SA',EC:'SA',
  AU:'OC',NZ:'OC',
  ZA:'AF',EG:'AF',MA:'AF',TN:'AF',DZ:'AF',KE:'AF',BW:'AF',ZM:'AF',CI:'AF',CV:'AF',
};

export function getContinent(cc: string | null | undefined): string {
  return (cc && CONTINENT_MAP[cc]) || 'XX';
}

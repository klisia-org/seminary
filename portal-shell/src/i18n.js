/**
 * The user's language for every portal (aretenic decision 071).
 *
 * Each portal's boot ships `lang` (frappe.local.lang) as `window.lang`; nothing else
 * from sysdefaults, so dates, numbers and times follow the language's own conventions.
 * Without a boot language (a page that does not ship one) the browser's is used.
 */
export function userLanguage() {
  return (typeof window !== 'undefined' && window.lang) || navigator.language || 'en'
}

/**
 * BCP 47 tag for `Intl` and `toLocaleString`. Frappe's bare `pt` is Brazilian Portuguese
 * here, and Frappe writes `pt_BR`-style codes with an underscore on some sites.
 */
export function userLocale() {
  const lang = String(userLanguage()).replace('_', '-')
  const tag = lang.toLowerCase() === 'pt' ? 'pt-BR' : lang
  try {
    return Intl.getCanonicalLocales(tag)[0]
  } catch {
    return 'en'
  }
}

/**
 * The dayjs locale name for the user, among those the portals import (`es`, `pt-br`).
 * portal-shell does not import dayjs itself: a bundled copy would be a second instance,
 * and frappe-ui's date components read the host app's.
 */
export function dayjsLocale() {
  const tag = userLocale().toLowerCase()
  if (tag.startsWith('pt')) return 'pt-br'
  if (tag.startsWith('es')) return 'es'
  return 'en'
}

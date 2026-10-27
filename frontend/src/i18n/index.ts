import { useSyncExternalStore } from 'react';
import hindi from './hi.json';
import help from './hi-help.json';
import domain from './hi-domain.json';
import dynamic from './hi-dynamic.json';

export type Language = 'en' | 'hi';
export const LANGUAGE_KEY = 'pramaan.language';
const dictionary: Record<string, string> = {...hindi, ...help, ...domain, ...dynamic};
const listeners = new Set<() => void>();
function subscribe(listener: () => void) { listeners.add(listener); return () => {listeners.delete(listener);}; }
function savedLanguage(): Language {
  try { return localStorage.getItem(LANGUAGE_KEY) === 'hi' ? 'hi' : 'en'; } catch { return 'en'; }
}
let language: Language = savedLanguage();
function applyDocumentLanguage() {
  if (typeof document !== 'undefined') document.documentElement.lang = language;
}
export function setLanguage(value: Language) {
  if (value !== 'hi' && value !== 'en') return;
  language = value;
  try { localStorage.setItem(LANGUAGE_KEY, value); } catch { /* Preference still works in memory. */ }
  applyDocumentLanguage();
  [...listeners].forEach(listener => listener());
}
export function useLanguage(): Language {
  return useSyncExternalStore(subscribe,
    () => language, () => 'en');
}
export function t(source: string, values: Record<string, string | number> = {}): string {
  const key = source.trim();
  const text = language === 'hi' ? dictionary[key] ?? key : key === 'Open status' ? 'Open' : key;
  const rendered = text.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.hasOwn(values, name) ? String(values[name]) : match);
  return source.slice(0, source.length - source.trimStart().length) + rendered + source.slice(source.trimEnd().length);
}
/** Presentation-only code maps; keys and API values never change with language. */
export function localizedLabels<T extends Record<string, string>>(labels: T): T {
  return new Proxy(labels, {get(target, name, receiver) {
    const value = Reflect.get(target, name, receiver);
    return typeof value === 'string' ? t(value) : value;
  }});
}
if (typeof window !== 'undefined') {
  applyDocumentLanguage();
  window.addEventListener('storage', event => {
    if (event.key === LANGUAGE_KEY || event.key === null) {
      language = savedLanguage(); applyDocumentLanguage(); [...listeners].forEach(listener => listener());
    }
  });
}

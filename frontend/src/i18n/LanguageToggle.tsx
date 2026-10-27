import { setLanguage, useLanguage } from './index';

export function LanguageToggle() {
  const language = useLanguage();
  return <div className="language-toggle" role="group" aria-label="Language / भाषा">
    <button type="button" lang="en" aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>🇬🇧 English</button>
    <button type="button" lang="hi" aria-pressed={language === 'hi'} onClick={() => setLanguage('hi')}>🇮🇳 हिन्दी</button>
  </div>;
}

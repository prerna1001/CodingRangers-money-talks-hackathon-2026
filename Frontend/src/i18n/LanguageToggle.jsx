import { LANGUAGES, useLanguage } from './context'
import './LanguageToggle.css'

export default function LanguageToggle() {
  const { language, setLanguage, t, translationFailed } = useLanguage()

  return (
    <div
      className="lang-toggle"
      role="group"
      aria-label={t('Language')}
      title={translationFailed ? 'Translation service unavailable' : undefined}
    >
      {LANGUAGES.map((lang) => (
        <button
          key={lang.code}
          type="button"
          className={`lang-toggle__btn ${language === lang.code ? 'lang-toggle__btn--active' : ''}`}
          onClick={() => setLanguage(lang.code)}
          aria-pressed={language === lang.code}
          aria-label={t(lang.label)}
        >
          {lang.short}
        </button>
      ))}
      {translationFailed && <span className="lang-toggle__warn" aria-hidden="true">!</span>}
    </div>
  )
}

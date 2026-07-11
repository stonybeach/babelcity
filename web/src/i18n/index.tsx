import React, { createContext, useContext, useState, useCallback } from 'react'
import { en } from './en'
import { zh } from './zh'

type Locale = 'en' | 'zh'

const dictionaries = { en, zh }

interface I18nContextType {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: string, params?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextType | null>(null)

export const useI18n = () => {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used within I18nProvider')
  return ctx
}

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const saved = localStorage.getItem('babelcity-locale')
    return (saved === 'zh' ? 'zh' : 'en') as Locale
  })

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l)
    localStorage.setItem('babelcity-locale', l)
  }, [])

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      let value = (dictionaries[locale] as Record<string, string>)[key] || key
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          value = value.replace(`{${k}}`, String(v))
        })
      }
      return value
    },
    [locale],
  )

  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>
}

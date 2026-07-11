import React from 'react'
import { BookOpen, Wrench, ListTodo, Sun, Moon } from 'lucide-react'
import { useTheme } from './ThemeProvider'
import { useI18n } from '../i18n'

type Tab = 'projects' | 'tasks' | 'jobs'

interface NavbarProps {
  activeTab: Tab
  onTabChange: (tab: Tab) => void
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onTabChange }) => {
  const { dark, toggle } = useTheme()
  const { locale, setLocale, t } = useI18n()

  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: 'projects', label: t('nav.projects'), icon: BookOpen },
    { key: 'tasks', label: t('nav.tasks'), icon: Wrench },
    { key: 'jobs', label: t('nav.jobs'), icon: ListTodo },
  ]

  return (
    <nav className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <svg width="32" height="32" viewBox="0 0 100 100" fill="none">
          <rect x="35" y="20" width="30" height="60" rx="2" fill="#3b82f6"/>
          <polygon points="50,5 65,20 35,20" fill="#f59e0b"/>
          <rect x="42" y="30" width="6" height="8" rx="1" fill="#fff"/>
          <rect x="52" y="30" width="6" height="8" rx="1" fill="#fff"/>
          <rect x="42" y="42" width="6" height="8" rx="1" fill="#fff"/>
          <rect x="52" y="42" width="6" height="8" rx="1" fill="#fff"/>
          <rect x="42" y="54" width="6" height="8" rx="1" fill="#fff"/>
          <rect x="52" y="54" width="6" height="8" rx="1" fill="#fff"/>
          <path d="M10 80 Q50 60 90 80" stroke="#f59e0b" strokeWidth="3" fill="none"/>
          <circle cx="80" cy="35" r="10" fill="#f59e0b"/>
        </svg>
        <span className="text-xl font-bold text-gray-900 dark:text-gray-100">Babel City</span>
      </div>

      <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => onTabChange(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === key
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => setLocale(locale === 'en' ? 'zh' : 'en')}
          className="px-3 py-1.5 rounded-md text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          {locale === 'en' ? '中' : 'En'}
        </button>
        <button
          onClick={toggle}
          className="p-2 rounded-md text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          {dark ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      </div>
    </nav>
  )
}
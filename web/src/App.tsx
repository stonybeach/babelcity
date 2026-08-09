import React, { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from './components/ThemeProvider'
import { I18nProvider } from './i18n'
import { Navbar } from './components/Navbar'
import { ProjectsPage } from './pages/ProjectsPage'
import { ProjectEditor } from './pages/ProjectEditor'
import { GlossaryEditor } from './pages/GlossaryEditor'
import { BookViewer } from './pages/BookViewer'
import { TasksPage } from './pages/TasksPage'
import { JobsPage } from './pages/JobsPage'
import './index.css'

type Tab = 'projects' | 'tasks' | 'jobs'
type View = 'list' | 'editor' | 'glossary' | 'viewer'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
})

const UI_STATE_KEY = 'babelcity-ui'

function loadUiState(): Partial<{ activeTab: Tab; view: View; projectId: string | null; volumeId: string | null }> {
  try {
    const raw = localStorage.getItem(UI_STATE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return {
      activeTab: parsed.activeTab,
      view: parsed.view,
      projectId: parsed.projectId ?? null,
      volumeId: parsed.volumeId ?? null,
    }
  } catch {
    return {}
  }
}

function App() {
  const persisted = loadUiState()
  const [activeTab, setActiveTab] = useState<Tab>(persisted.activeTab ?? 'projects')
  const [view, setView] = useState<View>(persisted.view ?? 'list')
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(persisted.projectId ?? null)
  const [selectedVolumeId, setSelectedVolumeId] = useState<string | null>(persisted.volumeId ?? null)

  useEffect(() => {
    try {
      localStorage.setItem(
        UI_STATE_KEY,
        JSON.stringify({
          activeTab,
          view,
          projectId: selectedProjectId,
          volumeId: selectedVolumeId,
        }),
      )
    } catch {}
  }, [activeTab, view, selectedProjectId, selectedVolumeId])

  const navigateToViewer = (projectId: string, volumeId: string) => {
    setSelectedProjectId(projectId)
    setSelectedVolumeId(volumeId)
    setView('viewer')
  }

  const navigateToGlossary = (projectId: string) => {
    setSelectedProjectId(projectId)
    setView('glossary')
  }

  const navigateToEditor = (projectId: string) => {
    setSelectedProjectId(projectId)
    setView('editor')
  }

  const goBack = () => setView('list')

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
      <ThemeProvider>
        <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
          <Navbar activeTab={activeTab} onTabChange={setActiveTab} />
          <main>
            {activeTab === 'projects' && (
              view === 'list' ? (
                <ProjectsPage
                  onNavigateToViewer={navigateToViewer}
                  onNavigateToGlossary={navigateToGlossary}
                  onNavigateToEditor={navigateToEditor}
                />
              ) : view === 'editor' && selectedProjectId ? (
                <ProjectEditor
                  projectId={selectedProjectId}
                  onBack={goBack}
                  onViewVolume={navigateToViewer}
                />
              ) : view === 'glossary' && selectedProjectId ? (
                <GlossaryEditor
                  projectId={selectedProjectId}
                  onBack={goBack}
                />
              ) : view === 'viewer' && selectedProjectId && selectedVolumeId ? (
                <BookViewer
                  projectId={selectedProjectId}
                  volumeId={selectedVolumeId}
                  onBack={goBack}
                />
              ) : null
            )}
            {activeTab === 'tasks' && <TasksPage />}
            {activeTab === 'jobs' && <JobsPage />}
          </main>
        </div>
      </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  )
}

export default App
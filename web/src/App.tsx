import React, { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from './components/ThemeProvider'
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

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('projects')
  const [view, setView] = useState<View>('list')
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [selectedVolumeId, setSelectedVolumeId] = useState<string | null>(null)

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
    </QueryClientProvider>
  )
}

export default App
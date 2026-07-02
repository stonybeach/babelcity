import React, { useState, useCallback } from 'react'
import { BookOpen, Download, X, ChevronLeft, ChevronRight } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projects as projectsApi, chapters as chaptersApi } from '../services/api'
import { type Project } from '../types'

interface BookViewerProps {
  projectId: string
  volumeId: string
  onBack: () => void
}

export const BookViewer: React.FC<BookViewerProps> = ({ projectId, volumeId, onBack }) => {
  const queryClient = useQueryClient()
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null)
  const [modelType, setModelType] = useState<string>('')
  const [qaRound, setQaRound] = useState(0)
  const [availableModels, setAvailableModels] = useState<string[]>([''])
  const [availableQARounds, setAvailableQARounds] = useState<number[]>([0])
  const [chapters, setChapters] = useState<{ id: string, full_path: string, title: string }[]>([])

  // Keyboard navigation for chapters
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (chapters.length === 0 || !selectedChapter) return
      const idx = chapters.findIndex(ch => ch.id === selectedChapter)
      if (idx < 0) return
      if (e.key === 'ArrowLeft' && idx > 0) {
        e.preventDefault()
        setSelectedChapter(chapters[idx - 1].id)
      }
      if (e.key === 'ArrowRight' && idx < chapters.length - 1) {
        e.preventDefault()
        setSelectedChapter(chapters[idx + 1].id)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [chapters, selectedChapter])

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId),
  })

  const volume = project?.volumes.find((v: any) => v.id === volumeId)

  // Fetch available translations for dynamic dropdowns
  const { data: availTrans } = useQuery({
    queryKey: ['availableTranslations', volumeId],
    queryFn: () => chaptersApi.availableTranslations(volumeId),
    enabled: !!volumeId,
  })

  React.useEffect(() => {
    if (availTrans?.available) {
      const models = ['']
      Object.keys(availTrans.available).forEach(m => models.push(m))
      setAvailableModels(models.sort())
      // Set QA rounds based on selected model
      if (modelType && availTrans.available[modelType]) {
        setAvailableQARounds(availTrans.available[modelType])
      } else {
        setAvailableQARounds([0])
      }
    }
  }, [availTrans, modelType])

  // Fetch TOC from spine items + nav name mapping (always available)
  const { data: tocData, isLoading: tocLoading } = useQuery({
    queryKey: ['toc', volumeId],
    queryFn: () => chaptersApi.getTOC(volumeId),
    enabled: !!volumeId,
  })

  React.useEffect(() => {
    if (tocData?.toc) {
      const extracted: { id: string, title: string }[] = tocData.toc.map((entry: any) => ({
        id: entry.id,
        title: entry.title,
      }))
      setChapters(extracted)
      // Auto-select first chapter if none selected
      if (!selectedChapter && extracted.length > 0) {
        setSelectedChapter(extracted[0].id)
      }
    }
  }, [tocData])

  const { data: chapterHtml, isLoading: chapterLoading } = useQuery({
    queryKey: ['chapter', selectedChapter, modelType, qaRound],
    queryFn: () => selectedChapter ? chaptersApi.getChapter(volumeId, selectedChapter, modelType || undefined, qaRound) : null,
    enabled: !!selectedChapter,
  })

  const downloadEpub = useMutation({
    mutationFn: () => projectsApi.exportEpub(projectId, volume?.volume_number || '1', modelType, qaRound),
    onSuccess: async (response) => {
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${volume?.target_volume_title || project?.project_name}_${modelType}_${qaRound}.epub`
      a.click()
      URL.revokeObjectURL(url)
    },
  })

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <button onClick={onBack} className="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
          ← Back to Projects
        </button>
        <button
          onClick={() => downloadEpub.mutate()}
          disabled={downloadEpub.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
        >
          <Download size={16} /> Download EPUB
        </button>
      </div>

      {/* Options bar */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3 mb-4 flex items-center gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400">Model Type</label>
          <select
            value={modelType}
            onChange={e => {
              setModelType(e.target.value)
              setQaRound(0)
            }}
            className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
          >
            <option value="">Source (Original)</option>
            {availableModels.filter(m => m).map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400">QA Round</label>
          <select
            value={qaRound}
            onChange={e => setQaRound(parseInt(e.target.value))}
            className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
          >
            {availableQARounds.map(qr => (
              <option key={qr} value={qr}>{qr === 0 ? '0 (Original)' : qr.toString()}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Two panels */}
      <div className="flex gap-4 h-[calc(100vh-280px)]">
        {/* TOC Panel */}
        <div className="w-1/3 bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden flex flex-col">
          <div className="p-3 border-b border-gray-200 dark:border-gray-700 font-medium text-gray-900 dark:text-gray-100">
            Table of Contents
          </div>
          <div className="flex-1 overflow-y-auto">
            {tocLoading ? (
              <div className="p-4 text-center text-gray-400">Loading...</div>
            ) : chapters.length === 0 ? (
              <div className="p-4 text-center text-gray-400">No chapters found. Import an EPUB first.</div>
            ) : (
              <ul className="divide-y divide-gray-100 dark:divide-gray-700">
                {chapters.map(ch => (
                  <li key={ch.id}>
                    <button
                      onClick={() => setSelectedChapter(ch.id)}
                      className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 ${
                        selectedChapter === ch.id ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' : 'text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      {ch.title}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* IFrame Panel */}
        <div className="w-2/3 bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden flex flex-col">
          <div className="p-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <span className="font-medium text-gray-900 dark:text-gray-100">Chapter Viewer</span>
            {selectedChapter && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const idx = chapters.findIndex(ch => ch.id === selectedChapter)
                    if (idx > 0) setSelectedChapter(chapters[idx - 1].id)
                  }}
                  disabled={!selectedChapter || chapters.findIndex(ch => ch.id === selectedChapter) === 0}
                  className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Previous chapter"
                >
                  <ChevronLeft size={20} className="text-gray-700 dark:text-gray-300" />
                </button>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {chapters.findIndex(ch => ch.id === selectedChapter) + 1} / {chapters.length}
                </span>
                <button
                  onClick={() => {
                    const idx = chapters.findIndex(ch => ch.id === selectedChapter)
                    if (idx < chapters.length - 1) setSelectedChapter(chapters[idx + 1].id)
                  }}
                  disabled={!selectedChapter || chapters.findIndex(ch => ch.id === selectedChapter) >= chapters.length - 1}
                  className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Next chapter"
                >
                  <ChevronRight size={20} className="text-gray-700 dark:text-gray-300" />
                </button>
              </div>
            )}
          </div>
          <div className="flex-1">
            {selectedChapter ? (
              chapterLoading ? (
                <div className="p-8 text-center text-gray-400">Loading chapter...</div>
              ) : chapterHtml ? (
                <iframe
                  srcDoc={chapterHtml}
                  className="w-full h-full border-0"
                  title="Chapter"
                />
              ) : (
                <div className="p-8 text-center text-gray-400">Chapter not found</div>
              )
            ) : (
              <div className="p-8 text-center text-gray-400 flex items-center justify-center h-full">
                Select a chapter from the table of contents
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
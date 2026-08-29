import React, { useState } from 'react'
import { Plus, Pencil, Trash2, Table2, Eye, Upload, BookOpen, Save, X } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projects as projectsApi, glossary as glossaryApi } from '../services/api'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorToast } from '../components/ErrorToast'
import { type Project } from '../types'
import { useI18n } from '../i18n'
import { getApiErrorMessage } from '../utils/errors'

interface ProjectsPageProps {
  onNavigateToViewer: (projectId: string, volumeId: string) => void
  onNavigateToGlossary: (projectId: string) => void
  onNavigateToEditor: (projectId: string) => void
}

export const ProjectsPage: React.FC<ProjectsPageProps> = ({
  onNavigateToViewer, onNavigateToGlossary, onNavigateToEditor,
}) => {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [errorToast, setErrorToast] = useState<string | null>(null)
  const [form, setForm] = useState({ project_name: '', source_title: '', project_type: 'Light Novel', source_language: 'ja', target_language: 'zh' })

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
    select: (data) => [...data].sort((a, b) => a.project_name.localeCompare(b.project_name)),
  })

  const createMutation = useMutation({
    mutationFn: (data: any) => projectsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowCreate(false)
      setForm({ project_name: '', source_title: '', project_type: 'Light Novel', source_language: 'ja', target_language: 'zh' })
    },
    onError: (err: any) => setErrorToast(getApiErrorMessage(err, t('projects.create.failed'))),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
    onError: (err: any) => setErrorToast(getApiErrorMessage(err, t('projects.delete.failed'))),
  })

  const isGeneric = form.project_type === 'Generic'

  const handleCreate = () => {
    if (!form.project_name.trim()) return
    if (isGeneric && (!form.source_language.trim() || !form.target_language.trim())) return
    createMutation.mutate(form)
  }

  const typeDisplay = (val: string) => val === 'Light Novel' ? t('projects.type.lightNovel') : val === 'Web Novel' ? t('projects.type.webNovel') : val === 'Generic' ? t('projects.type.generic') : val

  if (isLoading) return <div className="p-8 text-center text-gray-500">{t('projects.loading')}</div>

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('projects.title')}</h2>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          <Plus size={16} /> {t('projects.add')}
        </button>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">{t('projects.table.project')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">{t('projects.table.type')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">{t('projects.table.volumes')}</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">{t('projects.table.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {projects.map((p: Project) => (
              <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                <td className="px-4 py-3">
                  <button
                    onClick={() => onNavigateToEditor(p.id)}
                    className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
                  >
                    {p.project_name}
                  </button>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{p.source_title}</div>
                </td>
                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{typeDisplay(p.project_type)}</td>
                <td className="px-4 py-3">
                  {p.volumes.length === 0 ? (
                    <span className="text-sm text-gray-400">{t('projects.noVolumes')}</span>
                  ) : (
                    <div className="flex gap-2 flex-wrap">
                      {p.volumes.map(v => (
                        <button
                          key={v.id}
                          onClick={() => onNavigateToViewer(p.id, v.id)}
                          className="flex items-center gap-1 px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600"
                        >
                          <BookOpen size={14} /> {v.volume_number}
                        </button>
                      ))}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => onNavigateToGlossary(p.id)}
                      className="p-2 text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                      title={t('projects.action.glossary')}
                    >
                      <Table2 size={16} />
                    </button>
                    <button
                      onClick={() => onNavigateToEditor(p.id)}
                      className="p-2 text-yellow-600 dark:text-yellow-400 hover:text-yellow-800 dark:hover:text-yellow-300"
                      title={t('projects.action.edit')}
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(p.id)}
                      className="p-2 text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300"
                      title={t('projects.action.delete')}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {projects.length === 0 && (
          <div className="p-8 text-center text-gray-400">{t('projects.empty')}</div>
        )}
      </div>

      {/* Create Project Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('projects.create.title')}</h3>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('projects.create.name')}</label>
                <input
                  type="text"
                  value={form.project_name}
                  onChange={e => setForm(f => ({ ...f, project_name: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder={t('projects.create.placeholder.translated')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('projects.create.sourceTitle')}</label>
                <input
                  type="text"
                  value={form.source_title}
                  onChange={e => setForm(f => ({ ...f, source_title: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder={t('projects.create.placeholder.original')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('projects.create.type')}</label>
                <select
                  value={form.project_type}
                  onChange={e => setForm(f => ({
                    ...f,
                    project_type: e.target.value,
                    source_language: e.target.value === 'Generic' ? '' : 'ja',
                    target_language: e.target.value === 'Generic' ? '' : 'zh',
                  }))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                >
                  <option value="Light Novel">{t('projects.type.lightNovel')}</option>
                  <option value="Web Novel">{t('projects.type.webNovel')}</option>
                  <option value="Generic">{t('projects.type.generic')}</option>
                </select>
              </div>
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('projects.create.sourceLang')}</label>
                  <input
                    type="text"
                    maxLength={40}
                    value={form.source_language}
                    disabled={!isGeneric}
                    onChange={e => setForm(f => ({ ...f, source_language: e.target.value }))}
                    placeholder={isGeneric ? t('projects.create.langPlaceholder') : 'ja'}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:opacity-60"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('projects.create.targetLang')}</label>
                  <input
                    type="text"
                    maxLength={40}
                    value={form.target_language}
                    disabled={!isGeneric}
                    onChange={e => setForm(f => ({ ...f, target_language: e.target.value }))}
                    placeholder={isGeneric ? t('projects.create.langPlaceholder') : 'zh'}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:opacity-60"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">{t('projects.create.cancel')}</button>
              <button
                onClick={handleCreate}
                disabled={!form.project_name.trim() || (isGeneric && (!form.source_language.trim() || !form.target_language.trim())) || createMutation.isPending}
                className="px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {createMutation.isPending ? t('projects.create.submitting') : t('projects.create.submit')}
              </button>
            </div>
          </div>
        </div>
      )}

      {errorToast && <ErrorToast message={errorToast} onClose={() => setErrorToast(null)} />}

      <ConfirmDialog
        open={!!deleteConfirm}
        title={t('projects.delete.title')}
        message={t('projects.delete.message')}
        confirmText={t('projects.action.delete')}
        danger
        onConfirm={() => { if (deleteConfirm) { deleteMutation.mutate(deleteConfirm); setDeleteConfirm(null) } }}
        onCancel={() => setDeleteConfirm(null)}
      />
    </div>
  )
}

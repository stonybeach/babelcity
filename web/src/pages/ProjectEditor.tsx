import React, { useState, useRef } from 'react'
import { Plus, Pencil, Trash2, Upload, Eye, X, BookOpen, Check } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projects as projectsApi } from '../services/api'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorToast } from '../components/ErrorToast'
import { type Project } from '../types'
import { useI18n } from '../i18n'

interface ProjectEditorProps {
  projectId: string
  onBack: () => void
  onViewVolume: (projectId: string, volumeId: string) => void
}

export const ProjectEditor: React.FC<ProjectEditorProps> = ({ projectId, onBack, onViewVolume }) => {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [showAddVolume, setShowAddVolume] = useState(false)
  const [uploadDialog, setUploadDialog] = useState<{ volumeId: string, volumeNumber: string } | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [deleteVolumeConfirm, setDeleteVolumeConfirm] = useState<string | null>(null)
  const [volumeForm, setVolumeForm] = useState({ volume_number: '', source_volume_title: '', target_volume_title: '' })
  const [errorToast, setErrorToast] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState<{ volumeId: string, field: string, value: string } | null>(null)

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId),
  })

  const updateProject = useMutation({
    mutationFn: (data: any) => projectsApi.update(projectId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
  })

  const addVolume = useMutation({
    mutationFn: (data: any) => projectsApi.addVolume(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      setShowAddVolume(false)
      setVolumeForm({ volume_number: '', source_volume_title: '', target_volume_title: '' })
    },
  })

  const removeVolume = useMutation({
    mutationFn: ({ projectId, volumeNumber }: { projectId: string; volumeNumber: string }) =>
      projectsApi.removeVolume(projectId, volumeNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      setDeleteVolumeConfirm(null)
    },
  })

  const importEpub = useMutation({
    mutationFn: ({ volumeId, file }: { volumeId: string; file: File }) => {
      const volume = project?.volumes.find((v: any) => v.id === volumeId)
      if (!volume) throw new Error('Volume not found')
      return projectsApi.importEpub(projectId, volume.volume_number, file)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      setUploadDialog(null)
      setSelectedFile(null)
    },
  })

  const updateVolumeTitle = useMutation({
    mutationFn: ({ volumeNumber, data }: { volumeNumber: string; data: any }) =>
      projectsApi.updateVolume(projectId, volumeNumber, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
  })

  const typeDisplay = (val: string) => val === 'Light Novel' ? t('projects.type.lightNovel') : val === 'Web Novel' ? t('projects.type.webNovel') : val

  if (isLoading) return <div className="p-8 text-center text-gray-500">{t('editor.loading')}</div>
  if (!project) return <div className="p-8 text-center text-red-500">{t('editor.notFound')}</div>

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.size > 50 * 1024 * 1024) {
        setErrorToast(t('editor.error.fileSize'))
        return
      }
      if (!file.name.toLowerCase().endsWith('.epub')) {
        setErrorToast(t('editor.error.invalidFile'))
        return
      }
      setSelectedFile(file)
    }
  }

  const handleConfirmUpload = () => {
    if (uploadDialog && selectedFile) {
      importEpub.mutate({ volumeId: uploadDialog.volumeId, file: selectedFile })
    }
  }

  const handleCancelUpload = () => {
    setUploadDialog(null)
    setSelectedFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <button onClick={onBack} className="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
          {t('editor.back')}
        </button>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('editor.title')}</h2>
        <div />
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{t('editor.details')}</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('editor.field.projectName')}</label>
            <input
              type="text"
              defaultValue={project.project_name}
              onBlur={e => updateProject.mutate({ project_name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('editor.field.sourceTitle')}</label>
            <input
              type="text"
              defaultValue={project.source_title || ''}
              onBlur={e => updateProject.mutate({ source_title: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('editor.field.projectType')}</label>
            <select
              value={project.project_type}
              onChange={e => updateProject.mutate({ project_type: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            >
              <option value="Light Novel">{t('projects.type.lightNovel')}</option>
              <option value="Web Novel">{t('projects.type.webNovel')}</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('editor.field.sourceLang')}</label>
            <input
              type="text"
              defaultValue={project.source_language}
              onBlur={e => updateProject.mutate({ source_language: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('editor.field.targetLang')}</label>
            <input
              type="text"
              defaultValue={project.target_language}
              onBlur={e => updateProject.mutate({ target_language: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center gap-3 mb-4">
          {project.project_type === 'Light Novel' && (
            <button
              onClick={() => setShowAddVolume(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              <Plus size={16} /> {t('editor.addVolume')}
            </button>
          )}
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('editor.volumes')}</h3>
        </div>

        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">{t('editor.table.volume')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">{t('editor.table.sourceTitle')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">{t('editor.table.targetTitle')}</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">{t('editor.table.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {project.volumes.map((v: any) => (
              <tr key={v.id} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                <td className="px-4 py-3">
                  <button
                    onClick={() => onViewVolume(projectId, v.id)}
                    className="text-blue-600 dark:text-blue-400 hover:underline font-medium flex items-center gap-1"
                  >
                    <BookOpen size={14} /> {v.volume_number}
                  </button>
                </td>
                <td className="px-4 py-3">
                  <input
                    type="text"
                    defaultValue={v.source_volume_title || ''}
                    onBlur={e => updateVolumeTitle.mutate({ volumeNumber: v.volume_number, data: { source_volume_title: e.target.value } })}
                    className="w-full px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    type="text"
                    defaultValue={v.target_volume_title || ''}
                    onBlur={e => updateVolumeTitle.mutate({ volumeNumber: v.volume_number, data: { target_volume_title: e.target.value } })}
                    className="w-full px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                  />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => onViewVolume(projectId, v.id)}
                      className="p-2 text-gray-500 hover:text-blue-600"
                      title={t('editor.action.view')}
                    >
                      <Eye size={16} />
                    </button>
                    <button
                      onClick={() => setUploadDialog({ volumeId: v.id, volumeNumber: v.volume_number })}
                      className="p-2 text-gray-500 hover:text-green-600"
                      title={t('editor.action.upload')}
                    >
                      <Upload size={16} />
                    </button>
                    {project.project_type === 'Light Novel' && (
                      <button
                        onClick={() => setDeleteVolumeConfirm(v.volume_number)}
                        className="p-2 text-gray-500 hover:text-red-600"
                        title={t('editor.action.remove')}
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Volume Modal */}
      {showAddVolume && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('editor.addVolModal.title')}</h3>
              <button onClick={() => setShowAddVolume(false)} className="text-gray-500 hover:text-gray-700">
                <X size={20} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('editor.addVolModal.number')}</label>
                <input
                  type="text"
                  value={volumeForm.volume_number}
                  onChange={e => setVolumeForm({ ...volumeForm, volume_number: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder={t('editor.addVolModal.placeholder')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('editor.addVolModal.sourceTitle')}</label>
                <input
                  type="text"
                  value={volumeForm.source_volume_title}
                  onChange={e => setVolumeForm({ ...volumeForm, source_volume_title: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('editor.addVolModal.targetTitle')}</label>
                <input
                  type="text"
                  value={volumeForm.target_volume_title}
                  onChange={e => setVolumeForm({ ...volumeForm, target_volume_title: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowAddVolume(false)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                {t('projects.create.cancel')}
              </button>
              <button
                onClick={() => {
                  if (volumeForm.volume_number) {
                    addVolume.mutate(volumeForm)
                  }
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                {t('editor.addVolModal.submit')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EPUB Upload Dialog */}
      {uploadDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-full max-w-lg mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {t('editor.upload.title', { number: uploadDialog.volumeNumber })}
              </h3>
              <button onClick={handleCancelUpload} className="text-gray-500 hover:text-gray-700">
                <X size={20} />
              </button>
            </div>

            <label
              onDragOver={e => { e.preventDefault(); e.stopPropagation(); }}
              onDrop={e => {
                e.preventDefault()
                e.stopPropagation()
                const file = e.dataTransfer.files[0]
                if (file && file.name.toLowerCase().endsWith('.epub') && file.size <= 50 * 1024 * 1024) {
                  setSelectedFile(file)
                } else {
                  setErrorToast(t('editor.error.invalidFileUpload'))
                }
              }}
              className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500 dark:hover:border-blue-400 transition-colors block"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".epub"
                className="hidden"
                onChange={handleFileSelect}
              />
              {selectedFile ? (
                <div className="flex flex-col items-center">
                  <Check size={32} className="text-green-500 mb-2" />
                  <p className="text-gray-900 dark:text-gray-100 font-medium">{selectedFile.name}</p>
                  <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  <p className="text-blue-600 dark:text-blue-400 text-sm mt-2">{t('editor.upload.changeFile')}</p>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <Upload size={32} className="text-gray-400 mb-2" />
                  <p className="text-gray-600 dark:text-gray-300 font-medium">{t('editor.upload.dragDrop')}</p>
                  <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">{t('editor.upload.clickSelect')}</p>
                </div>
              )}
            </label>

            {importEpub.isPending && (
              <div className="mt-4">
                <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 dark:border-blue-400 border-t-transparent"></div>
                  <span className="text-sm">{t('editor.upload.uploading')}</span>
                </div>
              </div>
            )}

            {importEpub.isError && (
              <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
                <p className="text-red-600 dark:text-red-400 text-sm">{t('editor.upload.failed')}</p>
              </div>
            )}

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={handleCancelUpload}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                disabled={importEpub.isPending}
              >
                {t('projects.create.cancel')}
              </button>
              <button
                onClick={handleConfirmUpload}
                disabled={!selectedFile || importEpub.isPending}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <Upload size={16} />
                {importEpub.isPending ? t('editor.upload.submitting') : t('editor.upload.submit')}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteVolumeConfirm}
        title={t('editor.remove.title')}
        message={t('editor.remove.message', { number: deleteVolumeConfirm! })}
        confirmText={t('editor.remove.confirm')}
        danger
        onConfirm={() => removeVolume.mutate({ projectId, volumeNumber: deleteVolumeConfirm! })}
        onCancel={() => setDeleteVolumeConfirm(null)}
      />

      {errorToast && <ErrorToast message={errorToast} onClose={() => setErrorToast(null)} />}
    </div>
  )
}

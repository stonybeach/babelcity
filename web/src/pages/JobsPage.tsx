import React, { useState } from 'react'
import { Plus, Play, Pause, Trash2, ArrowUp, ArrowDown, ArrowUpToLine, ArrowDownToLine, Repeat, X } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jobs as jobsApi, tasks as tasksApi, projects as projectsApi } from '../services/api'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { useJobWebSocket } from '../hooks/useJobWebSocket'
import { type Job, type TaskDefinition, type Project } from '../types'

export const JobsPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [formType, setFormType] = useState<'Glossary' | 'Translation' | 'QA'>('Glossary')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [form, setForm] = useState({
    project_id: '', volume_number: '', task_id: '',
    resume: true, add_only: false, pre_translated_terms: '',
    start_version: 0, num_passes: 1,
  })

  useJobWebSocket()

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list(),
    refetchInterval: 5000,
  })

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => tasksApi.list(),
  })

  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })

  const startQueue = useMutation({
    mutationFn: () => jobsApi.start(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const pauseQueue = useMutation({
    mutationFn: () => jobsApi.pause(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const addJob = useMutation({
    mutationFn: ({ type, data }: { type: string; data: any }) => {
      if (type === 'Glossary') return jobsApi.addGlossary(data)
      if (type === 'Translation') return jobsApi.addTranslation(data)
      return jobsApi.addQA(data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setShowForm(false)
      resetForm()
    },
  })

  const removeJob = useMutation({
    mutationFn: (id: string) => jobsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const moveJob = useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: string }) => jobsApi.move(id, direction),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const repeatJob = useMutation({
    mutationFn: (id: string) => jobsApi.repeat(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const resetForm = () => {
    setForm({ project_id: '', volume_number: '', task_id: '', resume: true, add_only: false, pre_translated_terms: '', start_version: 0, num_passes: 1 })
    setShowForm(false)
  }

  const handleCreateClick = (type: 'Glossary' | 'Translation' | 'QA') => {
    setFormType(type)
    setShowForm(true)
  }

  const handleSubmit = () => {
    if (!form.project_id) { alert('Please select a project'); return }
    if (!form.volume_number) { alert('Please select a volume'); return }
    if (!form.task_id) { alert('Please select a task definition'); return }

    const filteredForm: any = {
      project_id: form.project_id,
      volume_number: form.volume_number,
      task_id: form.task_id,
    }
    if (formType === 'Glossary') {
      filteredForm.resume = form.resume
      filteredForm.add_only = form.add_only
      filteredForm.pre_translated_terms = form.pre_translated_terms
    } else if (formType === 'Translation') {
      filteredForm.resume = form.resume
    } else {
      filteredForm.start_version = form.start_version
      filteredForm.num_passes = form.num_passes
    }
    addJob.mutate({ type: formType, data: filteredForm })
  }

  const filteredTasks = (tasks as TaskDefinition[]).filter((t: TaskDefinition) => t.config_type === formType)
  const selectedProject = (projects as Project[]).find((p: Project) => p.id === form.project_id)

  if (isLoading) return <div className="p-8 text-center text-gray-500">Loading jobs...</div>

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button onClick={() => handleCreateClick('Glossary')} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
            <Plus size={16} /> Glossary Job
          </button>
          <button onClick={() => handleCreateClick('Translation')} className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700">
            <Plus size={16} /> Translation Job
          </button>
          <button onClick={() => handleCreateClick('QA')} className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700">
            <Plus size={16} /> QA Job
          </button>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => startQueue.mutate()} className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700">
            <Play size={16} /> Start
          </button>
          <button onClick={() => pauseQueue.mutate()} className="flex items-center gap-2 px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700">
            <Pause size={16} /> Pause
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Type</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Project</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Volume</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Progress</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {jobs.map((j: Job) => (
              <tr key={j.id} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    j.job_type === 'Glossary' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                    j.job_type === 'Translation' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                    'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                  }`}>
                    {j.job_type}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">{j.project_name}</td>
                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{j.volume_number}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    j.status === 'Running' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                    j.status === 'Completed' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                    j.status === 'Failed' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                    'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                  }`}>
                    {j.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">
                  {j.status === 'Running' && j.total > 0 ? (
                    <div className="flex items-center gap-2">
                      <div className="w-24 bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                        <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${(j.current / j.total) * 100}%` }} />
                      </div>
                      <span className="text-xs">{j.current}/{j.total}</span>
                    </div>
                  ) : j.status === 'Completed' ? (
                    <span className="text-green-600 dark:text-green-400">Done</span>
                  ) : j.status === 'Failed' ? (
                    <span className="text-red-600 dark:text-red-400" title={j.result_message || 'Error'}>Failed</span>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    {j.status === 'Pending' && (
                      <>
                        <button onClick={() => moveJob.mutate({ id: j.id, direction: 'up' })} className="p-1 text-gray-500 hover:text-blue-600" title="Move up"><ArrowUp size={14} /></button>
                        <button onClick={() => moveJob.mutate({ id: j.id, direction: 'down' })} className="p-1 text-gray-500 hover:text-blue-600" title="Move down"><ArrowDown size={14} /></button>
                        <button onClick={() => moveJob.mutate({ id: j.id, direction: 'top' })} className="p-1 text-gray-500 hover:text-blue-600" title="Move to top"><ArrowUpToLine size={14} /></button>
                        <button onClick={() => moveJob.mutate({ id: j.id, direction: 'bottom' })} className="p-1 text-gray-500 hover:text-blue-600" title="Move to bottom"><ArrowDownToLine size={14} /></button>
                      </>
                    )}
                    {j.status === 'Completed' && (
                      <button onClick={() => repeatJob.mutate(j.id)} className="p-1 text-gray-500 hover:text-green-600" title="Repeat"><Repeat size={14} /></button>
                    )}
                    {j.status === 'Failed' && (
                      <button onClick={() => repeatJob.mutate(j.id)} className="p-1 text-red-500 hover:text-red-600" title="Repeat (Failed)"><Repeat size={14} /></button>
                    )}
                    <button onClick={() => setDeleteConfirm(j.id)} className="p-1 text-gray-500 hover:text-red-600" title="Delete"><Trash2 size={14} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {jobs.length === 0 && <div className="p-8 text-center text-gray-400">No jobs in the queue.</div>}
      </div>

      {/* Job Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-full max-w-lg mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Add {formType} Job</h3>
              <button onClick={resetForm}><X size={20} className="text-gray-400" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Project *</label>
                <select value={form.project_id} onChange={e => setForm(f => ({ ...f, project_id: e.target.value, volume_number: '' }))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                  <option value="">Select project</option>
                  {projects.sort((a: Project, b: Project) => a.project_name.localeCompare(b.project_name)).map((p: Project) => (
                    <option key={p.id} value={p.id}>{p.project_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Volume *</label>
                <select value={form.volume_number} onChange={e => setForm(f => ({ ...f, volume_number: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                  <option value="">Select volume</option>
                  {selectedProject?.volumes.sort((a, b) => a.volume_number.localeCompare(b.volume_number)).map(v => (
                    <option key={v.id} value={v.volume_number}>{v.volume_number}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{formType} Config *</label>
                <select value={form.task_id} onChange={e => setForm(f => ({ ...f, task_id: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                  <option value="">Select config</option>
                  {filteredTasks.sort((a: TaskDefinition, b: TaskDefinition) => a.config_name.localeCompare(b.config_name)).map(t => (
                    <option key={t.id} value={t.id}>{t.config_name}</option>
                  ))}
                </select>
              </div>
              {formType === 'Glossary' && (
                <>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={form.resume} onChange={e => setForm(f => ({ ...f, resume: e.target.checked }))} />
                    <span className="text-sm text-gray-700 dark:text-gray-300">Resume (skip scanned)</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={form.add_only} onChange={e => setForm(f => ({ ...f, add_only: e.target.checked }))} />
                    <span className="text-sm text-gray-700 dark:text-gray-300">Add only (don't remove)</span>
                  </label>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Pre-translated terms</label>
                    <textarea value={form.pre_translated_terms} onChange={e => setForm(f => ({ ...f, pre_translated_terms: e.target.value }))}
                      rows={4} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                      placeholder="Source => Translation # Comment" />
                  </div>
                </>
              )}
              {formType === 'Translation' && (
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={form.resume} onChange={e => setForm(f => ({ ...f, resume: e.target.checked }))} />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Resume (skip translated)</span>
                </label>
              )}
              {formType === 'QA' && (
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Start Version</label>
                    <input type="number" value={form.start_version} onChange={e => setForm(f => ({ ...f, start_version: parseInt(e.target.value) || 0 }))}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                  </div>
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Number of Passes</label>
                    <input type="number" value={form.num_passes} onChange={e => setForm(f => ({ ...f, num_passes: parseInt(e.target.value) || 1 }))}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                  </div>
                </div>
              )}
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={resetForm} className="px-4 py-2 rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300">Cancel</button>
              <button onClick={handleSubmit} disabled={!form.project_id || !form.volume_number || !form.task_id}
                className="px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                Add Job
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Job"
        message="Are you sure you want to remove this job?"
        confirmText="Delete" danger
        onConfirm={() => { if (deleteConfirm) { removeJob.mutate(deleteConfirm); setDeleteConfirm(null) } }}
        onCancel={() => setDeleteConfirm(null)}
      />
    </div>
  )
}
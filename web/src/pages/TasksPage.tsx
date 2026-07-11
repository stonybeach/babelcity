import React, { useState } from 'react'
import { Edit, Trash2, Star, Plus, Save, X, Zap } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tasks as tasksApi } from '../services/api'
import { TaskDefinition } from '../types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorToast } from '../components/ErrorToast'
import { SuccessToast } from '../components/SuccessToast'

export const TasksPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [filterType, setFilterType] = useState<string>('')
  const [editingTask, setEditingTask] = useState<TaskDefinition | null>(null)
  const [form, setForm] = useState<Partial<TaskDefinition>>({})
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [errorToast, setErrorToast] = useState<string | null>(null)
  const [successToast, setSuccessToast] = useState<string | null>(null)
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')

  const { data: taskDefs, isLoading } = useQuery({
    queryKey: ['tasks', filterType],
    queryFn: () => tasksApi.list(filterType || undefined),
    select: (data) => [...data].sort((a, b) => {
      const typeCmp = (a.task_type ?? '').localeCompare(b.task_type ?? '');
      return typeCmp !== 0 ? typeCmp : (a.config_name ?? '').localeCompare(b.config_name ?? '');
    }),
  })

  const updateMutation = useMutation({
    mutationFn: (data: Partial<TaskDefinition>) => tasksApi.update(data.id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setEditingTask(null)
      setForm({})
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => tasksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setDeleteConfirm(null)
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => tasksApi.setDefault(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const createMutation = useMutation({
    mutationFn: (data: Partial<TaskDefinition>) => tasksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setEditingTask(null)
      setForm({})
    },
  })

  const startEditing = (task: TaskDefinition) => {
    setEditingTask(task)
    setForm({ ...task })
  }

  const handleSave = () => {
    if (!form.config_name || !form.config_name.trim()) {
      setErrorToast('Config Name is required')
      return
    }
    if (!form.model || !form.model.trim()) {
      setErrorToast('Model is required')
      return
    }
    if (!form.base_url || !form.base_url.trim()) {
      setErrorToast('Base URL is required')
      return
    }
    const cfgType = (form.config_type || '').toLowerCase()
    if ((cfgType === 'translation' || cfgType === 'qa') && (!form.model_type || !form.model_type.trim())) {
      setErrorToast('Model Type is required for ' + (form.config_type || '') + ' tasks')
      return
    }
    const normalizedForm = { ...form, config_type: cfgType === 'qa' ? 'QA' : (form.config_type || '').charAt(0).toUpperCase() + (form.config_type || '').slice(1) }
    if (editingTask) {
      updateMutation.mutate(normalizedForm)
    } else {
      createMutation.mutate(normalizedForm)
    }
  }

  const createTask = (type: string) => {
    setEditingTask(null)
    const capitalizedType = type === 'qa' ? 'QA' : type.charAt(0).toUpperCase() + type.slice(1)
    setForm({
      config_type: capitalizedType,
      config_name: '',
      base_url: 'http://localhost:8080/v1',
      api_key: 'not-needed',
      model: 'default',
      max_tokens: 8192,
      temperature: 0.7,
      top_p: 1.0,
      min_p: null,
      top_k: null,
      presence_penalty: 0,
      frequency_penalty: 0,
      repetition_penalty: 1.1,
      chunk_size: 12,
      history: 12,
      use_mini_glossary: true,
      synchronize_quotes: true,
      traditional_chinese: true,
      threads: type === 'glossary' ? 1 : 1,
      retry_attempts: 2,
    })
  }

  const handleDelete = () => {
    if (deleteConfirm) {
      deleteMutation.mutate(deleteConfirm)
    }
  }

  const handleSetDefault = (task: TaskDefinition) => {
    setDefaultMutation.mutate(task.id)
  }

  const handleTestConnection = async () => {
    if (!form.base_url || !form.api_key || !form.model) {
      setErrorToast('Base URL, API Key, and Model are required to test connection')
      return
    }
    setTestStatus('testing')
    try {
      const result = await tasksApi.testConnection({
        base_url: form.base_url,
        api_key: form.api_key,
        model: form.model,
      })
      if (result.success) {
        setTestStatus('success')
        setSuccessToast(result.message || 'Connection successful!')
      }
    } catch (err: any) {
      setTestStatus('error')
      setErrorToast(err.response?.data?.detail || 'Connection failed')
    }
  }

  const inputClass = "w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
  const labelClass = "block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"

  if (editingTask || form.config_type) {
    const isEditing = !!editingTask
    const isGlossary = form.config_type === 'Glossary'
    const isQA = form.config_type === 'QA'
    return (
      <>
        <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{isEditing ? 'Edit Task Definition' : 'New Task Definition'}</h2>
          <div className="flex gap-3">
            <button onClick={handleSave} className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
              <Save size={16} /> Save
            </button>
            <button onClick={() => { setEditingTask(null); setForm({}) }} className="flex items-center gap-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">
              <X size={16} /> Cancel
            </button>
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Config Name</label>
            <input className={inputClass} value={form.config_name || ''} onChange={e => setForm({ ...form, config_name: e.target.value })} />
          </div>
          <div>
            <label className={labelClass}>Config Type</label>
            <select className={inputClass} value={form.config_type || 'Translation'} onChange={e => setForm({ ...form, config_type: e.target.value })}>
              <option value="Glossary">Glossary</option>
              <option value="Translation">Translation</option>
              <option value="QA">QA</option>
            </select>
          </div>
          <div className="col-span-2">
            <label className={labelClass}>Base URL</label>
            <div className="flex gap-2">
              <input
                className={`${inputClass} flex-1 ${testStatus === 'success' ? '!bg-green-100 dark:!bg-green-900' : testStatus === 'error' ? '!bg-red-100 dark:!bg-red-900' : ''}`}
                value={form.base_url || ''}
                onChange={e => { setForm({ ...form, base_url: e.target.value }); setTestStatus('idle') }}
              />
              <button
                onClick={handleTestConnection}
                disabled={testStatus === 'testing'}
                className="flex items-center gap-1 px-3 py-2 bg-yellow-500 text-white rounded-md hover:bg-yellow-600 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                <Zap size={16} /> {testStatus === 'testing' ? 'Testing...' : 'Test Connection'}
              </button>
            </div>
          </div>
          <div>
            <label className={labelClass}>API Key</label>
            <input className={inputClass} type="password" value={form.api_key || ''} onChange={e => setForm({ ...form, api_key: e.target.value })} />
          </div>
          <div>
            <label className={labelClass}>Model</label>
            <input className={inputClass} value={form.model || ''} onChange={e => setForm({ ...form, model: e.target.value })} />
          </div>
          <div>
            <label className={labelClass}>Max Tokens</label>
            <input className={inputClass} type="number" value={form.max_tokens || 4096} onChange={e => setForm({ ...form, max_tokens: parseInt(e.target.value) || 4096 })} />
          </div>
          <div>
            <label className={labelClass}>Temperature</label>
            <input className={inputClass} type="number" step="0.1" value={form.temperature ?? ''} onChange={e => setForm({ ...form, temperature: e.target.value ? parseFloat(e.target.value) : null })} />
          </div>
          <div>
            <label className={labelClass}>Top P</label>
            <input className={inputClass} type="number" step="0.01" value={form.top_p ?? ''} onChange={e => setForm({ ...form, top_p: e.target.value ? parseFloat(e.target.value) : null })} />
          </div>
          <div>
            <label className={labelClass}>Min P</label>
            <input className={inputClass} type="number" step="0.01" value={form.min_p ?? ''} onChange={e => setForm({ ...form, min_p: e.target.value ? parseFloat(e.target.value) : null })} />
          </div>
          <div>
            <label className={labelClass}>Top K</label>
            <input className={inputClass} type="number" value={form.top_k ?? ''} onChange={e => setForm({ ...form, top_k: e.target.value ? parseInt(e.target.value) : null })} />
          </div>
          <div>
            <label className={labelClass}>Presence Penalty</label>
            <input className={inputClass} type="number" step="0.1" value={form.presence_penalty ?? ''} onChange={e => setForm({ ...form, presence_penalty: e.target.value ? parseFloat(e.target.value) : null })} />
          </div>
          <div>
            <label className={labelClass}>Frequency Penalty</label>
            <input className={inputClass} type="number" step="0.1" value={form.frequency_penalty ?? ''} onChange={e => setForm({ ...form, frequency_penalty: e.target.value ? parseFloat(e.target.value) : null })} />
          </div>
          <div>
            <label className={labelClass}>Repetition Penalty</label>
            <input className={inputClass} type="number" step="0.01" value={form.repetition_penalty ?? ''} onChange={e => setForm({ ...form, repetition_penalty: e.target.value ? parseFloat(e.target.value) : null })} />
          </div>
          <div>
            <label className={labelClass}>Chunk Size</label>
            <input className={inputClass} type="number" value={form.chunk_size || 2000} onChange={e => setForm({ ...form, chunk_size: parseInt(e.target.value) || 2000 })} />
          </div>
          <div>
            <label className={labelClass}>History</label>
            <input className={inputClass} type="number" value={form.history ?? ''} disabled={isGlossary || isQA} onChange={e => setForm({ ...form, history: e.target.value ? parseInt(e.target.value) : null })} />
          </div>
          <div>
            <label className={labelClass}>Threads</label>
            <input className={inputClass} type="number" value={isGlossary ? 1 : (form.threads || 1)} disabled={isGlossary} onChange={e => setForm({ ...form, threads: parseInt(e.target.value) || 1 })} />
          </div>
          <div>
            <label className={labelClass}>Retry Attempts</label>
            <input className={inputClass} type="number" value={form.retry_attempts || 3} onChange={e => setForm({ ...form, retry_attempts: parseInt(e.target.value) || 3 })} />
          </div>
          <div>
            <label className={labelClass}>Model Type</label>
            <input className={inputClass} value={form.model_type || ''} disabled={isGlossary} onChange={e => setForm({ ...form, model_type: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className={labelClass}>Override System Prompt</label>
            <textarea className={inputClass} rows={3} value={form.override_system_prompt || ''} disabled onChange={e => setForm({ ...form, override_system_prompt: e.target.value || null })} />
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" checked={!!form.use_mini_glossary} disabled={isGlossary} onChange={e => setForm({ ...form, use_mini_glossary: e.target.checked })} />
            <label className="text-sm text-gray-700 dark:text-gray-300">Use Mini Glossary</label>
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" checked={!!form.synchronize_quotes} onChange={e => setForm({ ...form, synchronize_quotes: e.target.checked })} />
            <label className="text-sm text-gray-700 dark:text-gray-300">Synchronize Quotes</label>
          </div>
          <div className="flex items-center gap-2">
            <input type="checkbox" checked={!!form.traditional_chinese} onChange={e => setForm({ ...form, traditional_chinese: e.target.checked })} />
            <label className="text-sm text-gray-700 dark:text-gray-300">Traditional Chinese</label>
          </div>
        </div>
      </div>
      {errorToast && <ErrorToast message={errorToast} onClose={() => setErrorToast(null)} />}
      {successToast && <SuccessToast message={successToast} onClose={() => setSuccessToast(null)} />}
    </>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Task Definitions</h2>
      </div>

      {/* Button bar with 3 add buttons */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => createTask('glossary')} className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          <Plus size={16} /> Glossary Config
        </button>
        <button onClick={() => createTask('translation')} className="flex items-center gap-1 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700">
          <Plus size={16} /> Translation Config
        </button>
        <button onClick={() => createTask('qa')} className="flex items-center gap-1 px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700">
          <Plus size={16} /> QA Config
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : !taskDefs || taskDefs.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No task definitions found.</div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Model</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Threads</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Default</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {taskDefs.map((task: TaskDefinition) => (
                <tr key={task.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">{task.config_name}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`px-2 py-1 rounded-full text-xs ${task.config_type === 'translation' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'}`}>
                      {task.config_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{task.model}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{task.threads}</td>
                  <td className="px-4 py-3 text-sm">
                    {task.is_default ? (
                      <span className="text-yellow-500">★ Default</span>
                    ) : (
                      <button onClick={() => handleSetDefault(task)} className="text-yellow-500 hover:text-yellow-600">
                        <Star size={14} /> Set Default
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm flex gap-2">
                    <button onClick={() => startEditing(task)} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
                      <Edit size={16} />
                    </button>
                    <button onClick={() => setDeleteConfirm(task.id)} className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300">
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Task Definition"
        message="Are you sure you want to delete this task definition? This cannot be undone."
        confirmText="Delete"
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteConfirm(null)}
      />

      {errorToast && <ErrorToast message={errorToast} onClose={() => setErrorToast(null)} />}
    </div>
  )
}

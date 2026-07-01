import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
})

export const projects = {
  list: () => api.get('/projects').then(r => r.data),
  get: (id: string) => api.get(`/projects/${id}`).then(r => r.data),
  create: (data: any) => api.post('/projects', data).then(r => r.data),
  update: (id: string, data: any) => api.put(`/projects/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/projects/${id}`).then(r => r.data),
  addVolume: (projectId: string, data: any) => api.post(`/projects/${projectId}/volumes`, data).then(r => r.data),
  updateVolume: (projectId: string, volumeNumber: string, data: any) =>
    api.put(`/projects/${projectId}/volumes/${volumeNumber}`, data).then(r => r.data),
  removeVolume: (projectId: string, volumeNumber: string) =>
    api.delete(`/projects/${projectId}/volumes/${volumeNumber}`).then(r => r.data),
  importEpub: (projectId: string, volumeNumber: string, file: File) => {
    const formData = new FormData()
    formData.append('epub_file', file)
    return api.post(`/projects/${projectId}/volumes/${volumeNumber}/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
  exportEpub: (projectId: string, volumeNumber: string, modelType: string = '', qaRound: number = 0) =>
    api.get(`/projects/${projectId}/volumes/${volumeNumber}/export`, {
      params: { model_type: modelType, qa_round: qaRound },
      responseType: 'blob',
    }),
}

export const tasks = {
  list: (type?: string) => api.get('/tasks', { params: { type } }).then(r => r.data),
  create: (data: any) => api.post('/tasks', data).then(r => r.data),
  update: (id: string, data: any) => api.put(`/tasks/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/tasks/${id}`).then(r => r.data),
  setDefault: (id: string) => api.post(`/tasks/${id}/default`).then(r => r.data),
}

export const jobs = {
  list: (status?: string) => api.get('/jobs', { params: { status } }).then(r => r.data),
  addGlossary: (data: any) => api.post('/jobs/glossary', data).then(r => r.data),
  addTranslation: (data: any) => api.post('/jobs/translation', data).then(r => r.data),
  addQA: (data: any) => api.post('/jobs/qa', data).then(r => r.data),
  start: () => api.post('/jobs/start').then(r => r.data),
  pause: () => api.post('/jobs/pause').then(r => r.data),
  remove: (id: string) => api.delete(`/jobs/${id}`).then(r => r.data),
  removeAll: (status: string = 'pending') => api.delete('/jobs', { params: { status } }).then(r => r.data),
  move: (id: string, direction: string) => api.post(`/jobs/${id}/move`, { direction }).then(r => r.data),
  repeat: (id: string) => api.post(`/jobs/${id}/repeat`).then(r => r.data),
}

export const glossary = {
  get: (projectId: string) => api.get(`/projects/${projectId}/glossary`).then(r => r.data),
  save: (projectId: string, glossary: Record<string, any>) =>
    api.put(`/projects/${projectId}/glossary`, { glossary }).then(r => r.data),
}

export const chapters = {
  getNav: (volumeId: string, modelType?: string, qaRound: number = 0) =>
    api.get(`/chapters/volumes/${volumeId}/nav`, { params: { model_type: modelType, qa_round: qaRound } }).then(r => r.data),
  getChapter: (volumeId: string, itemId: string, modelType?: string, qaRound: number = 0) =>
    api.get(`/chapters/volumes/${volumeId}/items/${itemId}`, { params: { model_type: modelType, qa_round: qaRound } }).then(r => r.data),
  getMeta: (itemId: string) => api.get(`/chapters/volumes/items/${itemId}/meta`).then(r => r.data),
  availableTranslations: (volumeId: string) =>
    api.get(`/chapters/volumes/${volumeId}/available_translations`).then(r => r.data),
}

export default api
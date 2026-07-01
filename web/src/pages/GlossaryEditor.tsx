import React, { useState } from 'react'
import { Save, X, Plus, Trash2 } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { glossary as glossaryApi } from '../services/api'
import { AgGridReact } from 'ag-grid-react'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'

interface GlossaryEditorProps {
  projectId: string
  onBack: () => void
}

export const GlossaryEditor: React.FC<GlossaryEditorProps> = ({ projectId, onBack }) => {
  const queryClient = useQueryClient()
  const [gridApi, setGridApi] = useState<any>(null)
  const [rowData, setRowData] = useState<any[]>([])
  const [unsaved, setUnsaved] = useState(false)

  const { data: glossaryData, isLoading } = useQuery({
    queryKey: ['glossary', projectId],
    queryFn: () => glossaryApi.get(projectId),
  })

  const saveMutation = useMutation({
    mutationFn: (glossary: Record<string, any>) => glossaryApi.save(projectId, glossary),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['glossary', projectId] })
      setUnsaved(false)
    },
  })

  React.useEffect(() => {
    if (glossaryData?.glossary) {
      const rows = Object.entries(glossaryData.glossary).map(([term, info]: [string, any]) => ({
        term,
        translated_name: info?.translated_name || '',
        type: info?.type || '',
        gender: info?.gender || '',
      }))
      setRowData(rows)
    }
  }, [glossaryData])

  const handleSave = () => {
    const glossary: Record<string, any> = {}
    rowData.forEach(row => {
      if (row.term) {
        glossary[row.term] = {
          translated_name: row.translated_name,
          type: row.type,
          gender: row.gender,
        }
      }
    })
    saveMutation.mutate(glossary)
  }

  const addRow = () => {
    const newRow = { term: '', translated_name: '', type: '', gender: '' }
    setRowData(prev => [...prev, newRow])
    setUnsaved(true)
  }

  const deleteSelected = () => {
    const selected = gridApi?.getSelectedRows()
    if (selected?.length) {
      const selectedIds = new Set(selected.map((r: any) => r.term))
      setRowData(prev => prev.filter(r => !selectedIds.has(r.term)))
      setUnsaved(true)
    }
  }

  const onCellChanged = (event: any) => {
    setUnsaved(true)
  }

  const columnDefs = [
    { field: 'term', headerName: 'Original Term', editable: true, minWidth: 150, checkboxSelection: true },
    { field: 'translated_name', headerName: 'Translated Name', editable: true, minWidth: 150 },
    { field: 'type', headerName: 'Type', editable: true, minWidth: 100 },
    { field: 'gender', headerName: 'Gender', editable: true, minWidth: 100 },
  ]

  if (isLoading) return <div className="p-8 text-center text-gray-500">Loading glossary...</div>

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <button onClick={onBack} className="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
          ← Back to Projects
        </button>
        <div className="flex items-center gap-3">
          {unsaved && <span className="text-sm text-yellow-600 dark:text-yellow-400">Unsaved changes</span>}
          <button
            onClick={handleSave}
            disabled={!unsaved || saveMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
          >
            <Save size={16} /> {saveMutation.isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <div className="flex items-center gap-3 mb-3">
          <button onClick={addRow} className="flex items-center gap-1 px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700">
            <Plus size={14} /> Add
          </button>
          <button onClick={deleteSelected} className="flex items-center gap-1 px-3 py-1 text-sm bg-red-600 text-white rounded-md hover:bg-red-700">
            <Trash2 size={14} /> Delete Selected
          </button>
        </div>

        <div className="ag-theme-alpine dark:bg-gray-700" style={{ height: 500, width: '100%' }}>
          <AgGridReact
            rowData={rowData}
            columnDefs={columnDefs}
            onGridReady={params => setGridApi(params.api)}
            onCellEditingStopped={onCellChanged}
            defaultColDef={{ resizable: true, sortable: true, filter: true }}
            rowSelection={{ mode: 'multiRow' }}
          />
        </div>
      </div>
    </div>
  )
}
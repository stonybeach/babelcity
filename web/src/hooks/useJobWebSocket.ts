import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'

interface JobMessage {
  type: string
  job_id?: string
  current?: number
  total?: number
  status?: string
  jobs?: any[]
}

export function useJobWebSocket(onProgress?: (jobId: string, current: number, total: number) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const queryClient = useQueryClient()
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/jobs`)

    ws.onmessage = (event) => {
      const msg: JobMessage = JSON.parse(event.data)
      if (msg.type === 'progress' && onProgress) {
        onProgress(msg.job_id!, msg.current!, msg.total!)
      }
      if (msg.type === 'job_list' || msg.type === 'status_change' || msg.type === 'progress') {
        queryClient.invalidateQueries({ queryKey: ['jobs'] })
      }
    }

    ws.onclose = () => {
      reconnectTimeout.current = setTimeout(connect, 3000)
    }

    wsRef.current = ws
  }, [queryClient, onProgress])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
    }
  }, [connect])
}
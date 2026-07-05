import React, { useEffect } from 'react'
import { XCircle, X } from 'lucide-react'

interface ErrorToastProps {
  message: string
  onClose: () => void
  duration?: number
}

export const ErrorToast: React.FC<ErrorToastProps> = ({ message, onClose, duration = 5000 }) => {
  useEffect(() => {
    if (duration) {
      const timer = setTimeout(onClose, duration)
      return () => clearTimeout(timer)
    }
  }, [duration, onClose])

  return (
    <div className="fixed top-4 right-4 z-[60] bg-red-600 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 max-w-md">
      <XCircle size={20} className="flex-shrink-0" />
      <span className="text-sm flex-1">{message}</span>
      <button onClick={onClose} className="flex-shrink-0 hover:opacity-80">
        <X size={16} />
      </button>
    </div>
  )
}

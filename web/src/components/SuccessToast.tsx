import React, { useEffect } from 'react'
import { CheckCircle, X } from 'lucide-react'

interface SuccessToastProps {
  message: string
  onClose: () => void
  duration?: number
}

export const SuccessToast: React.FC<SuccessToastProps> = ({ message, onClose, duration = 5000 }) => {
  useEffect(() => {
    if (duration) {
      const timer = setTimeout(onClose, duration)
      return () => clearTimeout(timer)
    }
  }, [duration, onClose])

  return (
    <div className="fixed top-4 right-4 z-[60] bg-green-600 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 max-w-md">
      <CheckCircle size={20} className="flex-shrink-0" />
      <span className="text-sm flex-1">{message}</span>
      <button onClick={onClose} className="flex-shrink-0 hover:opacity-80">
        <X size={16} />
      </button>
    </div>
  )
}

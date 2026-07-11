import React from 'react'
import { useI18n } from '../i18n'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  onConfirm: () => void
  onCancel: () => void
  confirmText?: string
  cancelText?: string
  danger?: boolean
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open, title, message, onConfirm, onCancel,
  confirmText, cancelText, danger = false,
}) => {
  const { t } = useI18n()
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">{title}</h3>
        <p className="text-gray-600 dark:text-gray-400 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            {cancelText || t('confirm.cancel')}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-md text-white ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}`}
          >
            {confirmText || t('confirm.confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
import { reactive } from 'vue'

export interface DialogInputSpec {
  placeholder: string
  match?: string
}

export interface DialogOptions {
  title: string
  message?: string
  confirmText?: string
  cancelText?: string
  showCancel?: boolean
  danger?: boolean
  input?: DialogInputSpec
}

export interface DialogResult {
  confirm: boolean
  value: string
}

export function useDialog() {
  const dialog = reactive({
    visible: false,
    title: '',
    message: '',
    confirmText: '确定',
    cancelText: '取消',
    showCancel: true,
    danger: false,
    input: null as DialogInputSpec | null
  })
  let resolver: ((result: DialogResult) => void) | null = null

  function openDialog(options: DialogOptions): Promise<DialogResult> {
    dialog.title = options.title
    dialog.message = options.message || ''
    dialog.confirmText = options.confirmText || '确定'
    dialog.cancelText = options.cancelText || '取消'
    dialog.showCancel = options.showCancel !== false
    dialog.danger = options.danger === true
    dialog.input = options.input || null
    dialog.visible = true
    return new Promise((resolve) => { resolver = resolve })
  }

  function settle(result: DialogResult) {
    dialog.visible = false
    const done = resolver
    resolver = null
    done?.(result)
  }

  return {
    dialog,
    openDialog,
    onDialogConfirm: (value: string) => settle({ confirm: true, value }),
    onDialogCancel: () => settle({ confirm: false, value: '' })
  }
}

export function useActionSheet() {
  const actionSheet = reactive({
    visible: false,
    items: [] as string[]
  })
  let resolver: ((index: number | null) => void) | null = null

  function openActionSheet(items: string[]): Promise<number | null> {
    actionSheet.items = items
    actionSheet.visible = true
    return new Promise((resolve) => { resolver = resolve })
  }

  function settle(index: number | null) {
    actionSheet.visible = false
    const done = resolver
    resolver = null
    done?.(index)
  }

  return {
    actionSheet,
    openActionSheet,
    onActionSheetSelect: (index: number) => settle(index),
    onActionSheetClose: () => settle(null)
  }
}

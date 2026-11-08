export const demoUsers = [
  { id: 'lumen_282506_00001', label: 'Free user', premium: false },
  { id: 'lumen_282506_00000', label: 'Premium user', premium: true },
] as const

export const demoActions = [
  { key: 'photo_import', label: 'Import photo' },
  { key: 'bg_remove', label: 'Remove background' },
  { key: 'ai_enhance', label: 'AI enhance' },
  { key: 'export', label: 'Export' },
  { key: 'export_hd_attempt', label: 'Export in full resolution' },
] as const

export type DemoAction = typeof demoActions[number]['key']
export const freeDailyEdits = 10

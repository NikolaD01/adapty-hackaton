export const demoUsers = [
  { id: 'lumen_282506_00007', label: 'Free user', accessLevel: null },
  { id: 'lumen_282506_00000', label: 'Premium user', accessLevel: 'premium' },
] as const

export const demoActions = [
  { key: 'photo_import', label: 'Import photo' },
  { key: 'bg_remove', label: 'Remove background' },
  { key: 'ai_enhance', label: 'AI enhance' },
  { key: 'export', label: 'Export' },
  { key: 'export_hd_attempt', label: 'Export in full resolution' },
] as const

export type DemoAction = typeof demoActions[number]['key']
export type DemoUser = typeof demoUsers[number]
export const freeDailyEdits = 10
export const blockedExport = 'pt_track_hd_export_blocked'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { flush, init, pending, setUser, shutdown, track } from 'feature-signal-sdk'
import { useEffect, useRef, useState } from 'react'
import { webEnv } from '../../shared/env'
import { blockedExport, demoUsers, freeDailyEdits, type DemoAction, type DemoUser } from './demoActions'

export function useDemoTracking(user: DemoUser, canExportHd: boolean | undefined) {
  const client = useQueryClient()
  const photoByUser = useRef<Record<string, string>>({})
  const [quota, setQuota] = useState<Record<string, number>>({})
  const editsLeft = user.accessLevel === null ? quota[user.id] ?? freeDailyEdits : null

  useEffect(() => {
    init({ baseUrl: webEnv.apiBase, appId: webEnv.appId, customerUserId: demoUsers[0].id })
    return shutdown
  }, [])

  const mutation = useMutation({
    mutationFn: async (action: DemoAction | null) => {
      setUser(user.id)
      if (action) {
        if (action === 'export_hd_attempt' && canExportHd === undefined) return
        if (action === 'ai_enhance' && editsLeft === 0) return
        if (!photoByUser.current[user.id] || action === 'photo_import') {
          photoByUser.current[user.id] = crypto.randomUUID()
        }
        const props = { photo_id: photoByUser.current[user.id], synthetic: true }
        if (action === 'ai_enhance' && editsLeft !== null) {
          const remaining = editsLeft - 1
          setQuota((previous) => ({ ...previous, [user.id]: remaining }))
          track(action, { ...props, edits_left: remaining })
        } else {
          track(action, props)
        }
        if (action === 'export_hd_attempt' && canExportHd === false) track(blockedExport, props)
      }

      const unknown = new Set<string>()
      // A retry timer can already be sending an older batch.
      do {
        const result = await flush()
        for (const key of result.unknown_keys) unknown.add(key)
      } while (pending().length > 0)

      await client.invalidateQueries({ queryKey: ['demo-user', user.id] })
      if (unknown.size > 0) {
        throw new Error(`Register these event keys before tracking: ${[...unknown].join(', ')}.`)
      }
    },
  })

  return { ...mutation, editsLeft }
}

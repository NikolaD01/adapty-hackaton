import { useMutation, useQueryClient } from '@tanstack/react-query'
import { flush, init, pending, setUser, shutdown, track } from 'feature-signal-sdk'
import { useEffect, useRef, useState } from 'react'
import { webEnv } from '../../shared/env'
import { demoUsers, freeDailyEdits } from './demoActions'
import type { DemoAction } from './demoActions'

export function useDemoTracking(user: typeof demoUsers[number]) {
  const client = useQueryClient()
  const photo = useRef<string>()
  const [editsLeft, setEditsLeft] = useState(freeDailyEdits)

  useEffect(() => {
    init({ baseUrl: webEnv.apiBase, appId: webEnv.appId, customerUserId: demoUsers[0].id })
    return shutdown
  }, [])

  return useMutation({
    mutationFn: async (action: DemoAction | null) => {
      setUser(user.id)
      if (action) {
        if (!photo.current || action === 'photo_import') photo.current = crypto.randomUUID()
        const props = { photo_id: photo.current, synthetic: true }
        if (action === 'ai_enhance' && !user.premium) {
          const remaining = Math.max(editsLeft - 1, 0)
          setEditsLeft(remaining)
          track(action, { ...props, edits_left: remaining })
        } else {
          track(action, props)
        }
        if (action === 'export_hd_attempt' && !user.premium) {
          track('pt_track_hd_export_blocked', props)
        }
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
}

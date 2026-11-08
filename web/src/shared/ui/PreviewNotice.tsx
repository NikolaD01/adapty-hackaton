import { webEnv } from '../env'

export function PreviewNotice() {
  if (!webEnv.useMocks) return null
  return <p className="preview-notice" role="status">Mock preview · synthetic data · Adapty is disconnected</p>
}

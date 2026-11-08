import type { ReactNode } from 'react'

export function PlaceholderPage({ title, description, actions }: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <header className="placeholder-page">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="targeting-actions page-actions">{actions}</div>}
    </header>
  )
}

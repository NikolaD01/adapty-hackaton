import type { ReactNode } from 'react'

export function ReviewList({ label, selectedId, items, onSelect }: {
  label: string
  selectedId: string
  items: { id: string; title: string; description: string; badge?: ReactNode }[]
  onSelect: (id: string) => void
}) {
  return (
    <section className="behavioral-panel review-list" aria-label={label}>
      <header className="review-list-heading">
        <h2>{label}</h2>
        <span className="data-tag">{items.length}</span>
      </header>
      <ul>
        {items.map(({ id, title, description, badge }) => (
          <li key={id}>
            <button type="button" aria-pressed={id === selectedId} onClick={() => onSelect(id)}>
              <span className="review-list-item">
                <span className="review-list-title">{title}</span>
                {badge}
              </span>
              <span className="review-list-description">{description}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

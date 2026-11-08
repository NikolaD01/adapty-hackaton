import type { ReactNode } from 'react'

export function TargetingTable({ label, headers, children }: {
  label: string
  headers: readonly string[]
  children: ReactNode
}) {
  return (
    <div className="table-scroll" role="region" aria-label={`${label} table area`} tabIndex={0}>
      <table className="targeting-table" aria-label={label}>
        <thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

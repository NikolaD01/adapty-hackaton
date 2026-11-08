import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import './select.css'

type Option<T> = { value: T; label: string }
type SelectProps<T extends string | number> = {
  label: string
  options: readonly Option<T>[]
  disabled?: boolean
} & (
  | { multiple?: false; value: T; onChange: (value: T) => void }
  | { multiple: true; value: readonly T[]; onChange: (value: T[]) => void; maxSelections: number }
)

export function Select<T extends string | number>(props: SelectProps<T>) {
  const { label, options, disabled } = props
  const id = useId()
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const expanded = open && !disabled && options.length > 0
  const active = Math.min(activeIndex, options.length - 1)
  const selected = (value: T) => props.multiple ? props.value.includes(value) : props.value === value
  const atLimit = props.multiple && props.value.length >= props.maxSelections
  const selection = options.filter(({ value }) => selected(value))

  useEffect(() => {
    if (!expanded) return
    function closeOutside(event: PointerEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [expanded])

  useEffect(() => {
    list.current?.children[active]?.scrollIntoView?.({ block: 'nearest' })
  }, [active, expanded])

  function show(fallback = 0) {
    const index = options.findIndex(({ value }) => selected(value))
    setActiveIndex(index < 0 ? fallback : index)
    setOpen(true)
  }

  function choose(value: T) {
    if (props.multiple) {
      if (selected(value)) props.onChange(props.value.filter((item) => item !== value))
      else if (!atLimit) props.onChange([...props.value, value])
      return
    }
    setOpen(false)
    if (!selected(value)) props.onChange(value)
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    switch (event.key) {
      case 'ArrowDown':
      case 'ArrowUp': {
        event.preventDefault()
        const down = event.key === 'ArrowDown'
        if (!expanded) show(down ? 0 : options.length - 1)
        else setActiveIndex(Math.max(0, Math.min(options.length - 1, active + (down ? 1 : -1))))
        break
      }
      case 'Home':
      case 'End':
        if (!expanded) break
        event.preventDefault()
        setActiveIndex(event.key === 'Home' ? 0 : options.length - 1)
        break
      case 'Enter':
      case ' ':
        if (!expanded) break
        event.preventDefault()
        choose(options[active].value)
        break
      case 'Escape':
        if (!expanded) break
        event.preventDefault()
        event.stopPropagation()
        setOpen(false)
        break
    }
  }

  return (
    <div className="custom-select" ref={root}>
      <button ref={trigger} type="button" className="custom-select-trigger" role="combobox"
        aria-label={label} aria-expanded={expanded} aria-controls={expanded ? id : undefined}
        aria-activedescendant={expanded ? `${id}-${active}` : undefined}
        disabled={disabled || !options.length} onBlur={() => setOpen(false)} onKeyDown={onKeyDown}
        onClick={() => expanded ? setOpen(false) : show()}>
        <span className="custom-select-value">
          {!options.length ? 'No options available' : props.multiple ? (
            selection.length ? selection.map(({ value, label: text }) => (
              <span className="custom-select-chip" key={value}>{text}</span>
            )) : 'Select features…'
          ) : selection[0]?.label ?? 'Select…'}
        </span>
        <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {expanded && (
        <ul className="custom-select-list" id={id} ref={list} role="listbox" aria-label={label}
          aria-multiselectable={props.multiple || undefined} onPointerDown={(event) => event.preventDefault()}>
          {options.map(({ value, label: text }, index) => (
            <li className="custom-select-option" id={`${id}-${index}`} key={value} role="option"
              aria-selected={selected(value)} aria-disabled={atLimit && !selected(value) || undefined}
              data-active={index === active} onClick={() => { trigger.current?.focus(); choose(value) }}>
              {props.multiple && <span className="custom-select-check" aria-hidden="true">{selected(value) && '✓'}</span>}
              <span>{text}</span>
              {!props.multiple && selected(value) && <span className="custom-select-mark" aria-hidden="true">✓</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

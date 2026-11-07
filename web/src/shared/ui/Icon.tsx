const shapes = {
  'chevron-down': <path d="m6 9 6 6 6-6" />,
  'chevrons-left': <path d="m11 6-6 6 6 6m7-12-6 6 6 6" />,
  gauge: <><path d="M3 18v-2a9 9 0 0 1 18 0v2H3Zm9-2 4-6M6 13l1 1m5-6v2m7 3-1 1" /><circle cx="12" cy="16" r="1" /></>,
  chart: <path d="M3 3v18h18M7 17v-4m4 4V9m4 8v-6m4 6V6" />,
  users: <><circle cx="12" cy="8" r="3" /><path d="M6 20v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2M3 16v-2a3 3 0 0 1 3-3m15 5v-2a3 3 0 0 0-3-3M4 6a2.5 2.5 0 0 0 0 5m16-5a2.5 2.5 0 0 1 0 5" /></>,
  product: <><rect x="3" y="4" width="18" height="17" rx="3" /><path d="M8 4v2a4 4 0 0 0 8 0V4" /></>,
  flow: <><path d="M13 21H6a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3h9a3 3 0 0 1 3 3v3M7 2v3h7V2m3 19v-8m-3 3 3-3 3 3" /><circle cx="20" cy="10" r="1" /></>,
  pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
  retention: <path d="M11 22H7a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v5M8 2v4h6V2m0 10h3l4 5-4 4-4-5v-4h1Zm2 3h.01" />,
  ab: <path d="m2 10 3-7 3 7M3 8h4m2 11L21 4m-7 10h4a2 2 0 0 1 0 4h-4v-4Zm0 4h4a2 2 0 0 1 0 4h-4v-4Z" />,
  activity: <path d="M2 12h5l3-7 4 14 3-7h5" />,
  demo: <><circle cx="7" cy="12" r="4" /><circle cx="17" cy="12" r="4" /><path d="M11 12h2M7 10v4m10-4v4" /></>,
  bell: <path d="M18 8a6 6 0 0 0-12 0c0 6-3 6-3 9 0 1 2 2 9 2s9-1 9-2c0-3-3-3-3-9Zm-8 13a2 2 0 0 0 4 0" />,
  external: <path d="M14 3h7v7m0-7-9 9m7 1v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6" />,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4m10-4v4M3 10h18" /></>,
  edit: <path d="m3 21 1-5L17 3a2 2 0 0 1 3 0l1 1a2 2 0 0 1 0 3L8 20l-5 1Zm12-16 4 4" />,
  plus: <path d="M12 4v16M4 12h16" />,
  columns: <path d="M3 21h18M6 15v2m0-8v3m6 2v3m0-13v7m6-2v8" />,
  dollar: <><circle cx="12" cy="12" r="10" /><path d="M15 8h-4a2 2 0 1 0 0 4h2a2 2 0 1 1 0 4H9m3-10v12" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01" /></>,
}

export type IconName = keyof typeof shapes

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {shapes[name]}
    </svg>
  )
}

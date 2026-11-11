// One small line-icon set, drawn at 1.6 stroke on a 20px grid so every
// control in the app shares a hand. Icons are decorative: the control that
// holds one carries the accessible name.
const PATHS = {
  speaker: (
    <>
      <path d="M3.5 8v4h2.8L10 15V5L6.3 8H3.5Z" />
      <path d="M13 7.5a3.5 3.5 0 0 1 0 5M15.2 5.3a6.6 6.6 0 0 1 0 9.4" />
    </>
  ),
  stop: <rect x="5.5" y="5.5" width="9" height="9" rx="1.5" />,
  mic: (
    <>
      <rect x="7.5" y="3" width="5" height="9" rx="2.5" />
      <path d="M4.8 9.6a5.2 5.2 0 0 0 10.4 0M10 14.8V17" />
    </>
  ),
  chat: <path d="M4 5.5h12v8H9.2L6 16.2v-2.7H4v-8Z" />,
  close: <path d="M5.5 5.5l9 9M14.5 5.5l-9 9" />,
  send: <path d="M4 10h11M10.5 5.5 15 10l-4.5 4.5" />,
}

export default function Icon({ name, className = '' }) {
  return (
    <svg
      className={`icon ${className}`}
      viewBox="0 0 20 20"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  )
}

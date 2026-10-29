// Auditor's tickmark. Only render it next to a figure that really was
// traced or checked — it is a claim, not decoration.
export default function Tick({ className = '', style, title }) {
  return (
    <svg
      className={`tick ${className}`}
      viewBox="0 0 16 16"
      style={style}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      <path d="M2.5 8.8l3.4 3.4L13.5 3.8" pathLength="1" />
    </svg>
  )
}

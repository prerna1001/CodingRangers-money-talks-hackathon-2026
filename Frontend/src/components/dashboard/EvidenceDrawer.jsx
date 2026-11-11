import { useEffect, useRef } from 'react'
import { ledgerChange, ledgerMoney } from '../../utils/format'
import './DriverTable.css'

// Side panel listing the source transactions behind one driver. Opened
// from the driver table and from any chart bar (see DriversView).
export default function EvidenceDrawer({ driver, evidence, loading, onClose }) {
  const closeRef = useRef(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  // Focus the drawer on open, close on Escape, and hand focus back to
  // whatever opened it when it closes. Runs once per open, not per render.
  useEffect(() => {
    const opener = document.activeElement
    closeRef.current?.focus()
    const onKey = (event) => {
      if (event.key === 'Escape') onCloseRef.current()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      opener?.focus?.()
    }
  }, [])

  return (
    <div className="evidence-drawer-overlay" onClick={onClose}>
      <div
        className="evidence-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="evidence-drawer__header">
          <div>
            <h2 id="evidence-title">{driver.driver}</h2>
            <p>{driver.account}, {ledgerChange(driver.amount)} this period</p>
          </div>
          <button ref={closeRef} type="button" className="evidence-drawer__close" onClick={onClose} aria-label="Close evidence">
            ×
          </button>
        </div>

        {loading && <p className="evidence-drawer__loading">Loading source transactions…</p>}

        {!loading && evidence && (
          <>
            <p className="evidence-drawer__intro">
              {evidence.transactions.length} source transactions behind this driver
            </p>
            <ul className="evidence-list">
              {evidence.transactions.map((tx) => (
                <li key={`${tx.date}-${tx.customer}`} className="evidence-item">
                  <div className="evidence-item__top">
                    <span className="evidence-item__customer">{tx.customer}</span>
                    <span className={tx.amount < 0 ? 'text-down' : ''}>{ledgerMoney(tx.amount)}</span>
                  </div>
                  <div className="evidence-item__meta">
                    <span>{tx.date}</span>
                    <span>{tx.category}</span>
                  </div>
                  <p className="evidence-item__memo">{tx.memo}</p>
                </li>
              ))}
            </ul>
            <p className="evidence-drawer__source">
              Source <code>{evidence.method} {evidence.url}</code>
            </p>
          </>
        )}
      </div>
    </div>
  )
}

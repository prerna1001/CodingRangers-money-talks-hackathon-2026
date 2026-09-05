import { useState } from 'react'
import { fetchDriverEvidence } from '../../services/mockApi'
import './DriverTable.css'

export default function DriverTable({ drivers }) {
  const [openDriver, setOpenDriver] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [loading, setLoading] = useState(false)

  const openEvidence = async (driver) => {
    setOpenDriver(driver)
    setLoading(true)
    const res = await fetchDriverEvidence(driver.driver)
    setEvidence(res)
    setLoading(false)
  }

  const closeEvidence = () => {
    setOpenDriver(null)
    setEvidence(null)
  }

  return (
    <div className="driver-table-wrap">
      <h3>Driver drilldown</h3>
      <p className="driver-table__subtitle">Click a row to see the source transactions behind it</p>

      <div className="driver-table__scroll">
        <table className="driver-table">
          <thead>
            <tr>
              <th>Account</th>
              <th>Current</th>
              <th>Prior</th>
              <th>Change</th>
              <th>% change</th>
              <th>Top driver</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {drivers.map((d) => (
              <tr key={d.driver} onClick={() => openEvidence(d)}>
                <td>{d.account}</td>
                <td>${d.current.toLocaleString()}</td>
                <td>${d.prior.toLocaleString()}</td>
                <td className={d.amount >= 0 ? 'text-up' : 'text-down'}>
                  {d.amount >= 0 ? '+' : ''}${d.amount.toLocaleString()}
                </td>
                <td className={d.amount >= 0 ? 'text-up' : 'text-down'}>
                  {d.share_of_change_pct >= 0 ? '+' : ''}
                  {d.share_of_change_pct}%
                </td>
                <td className="driver-table__driver-name">{d.driver}</td>
                <td>
                  <span className="confidence-pill">{Math.round(d.confidence * 100)}%</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {openDriver && (
        <div className="evidence-drawer-overlay" onClick={closeEvidence}>
          <div className="evidence-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="evidence-drawer__header">
              <div>
                <h4>{openDriver.driver}</h4>
                <p>{openDriver.account}</p>
              </div>
              <button type="button" className="evidence-drawer__close" onClick={closeEvidence} aria-label="Close">
                ×
              </button>
            </div>

            {loading && <p className="evidence-drawer__loading">Loading evidence…</p>}

            {!loading && evidence && (
              <>
                <div className="evidence-drawer__source">
                  <code>{evidence.method}</code> <code>{evidence.url}</code>
                </div>
                <ul className="evidence-list">
                  {evidence.transactions.map((tx) => (
                    <li key={`${tx.date}-${tx.customer}`} className="evidence-item">
                      <div className="evidence-item__top">
                        <span className="evidence-item__customer">{tx.customer}</span>
                        <span className={tx.amount >= 0 ? 'text-up' : 'text-down'}>
                          {tx.amount >= 0 ? '+' : ''}${tx.amount.toLocaleString()}
                        </span>
                      </div>
                      <div className="evidence-item__meta">
                        <span>{tx.date}</span>
                        <span>{tx.category}</span>
                      </div>
                      <p className="evidence-item__memo">{tx.memo}</p>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { fetchDriverEvidence } from '../../services/mockApi'
import './DriverTable.css'

function formatCurrency(value) {
  const numeric = Number(value) || 0
  const abs = Math.abs(numeric)
  const sign = numeric > 0 ? '+' : numeric < 0 ? '-' : ''
  return `${sign}$${abs.toLocaleString('en-US')}`
}

function formatPlainCurrency(value) {
  const numeric = Number(value) || 0
  const abs = Math.abs(numeric)
  const sign = numeric < 0 ? '-' : ''
  return `${sign}$${abs.toLocaleString('en-US')}`
}

function driverType(account) {
  const lowered = String(account || '').toLowerCase()
  if (lowered.includes('revenue') || lowered.includes('sales')) return 'Revenue'
  if (lowered.includes('refund')) return 'Contra'
  if (lowered.includes('hosting') || lowered.includes('cost') || lowered.includes('ads')) return 'Spend'
  return 'Driver'
}

export default function DriverTable({ drivers = [] }) {
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
      <div className="panel-heading panel-heading--table">
        <div>
          <h3>Driver Drilldown</h3>
          <p>Click a row to inspect the source transactions behind it</p>
        </div>
        <span className="driver-table__count">{drivers.length} ranked drivers</span>
      </div>

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
            {drivers.length === 0 && (
              <tr>
                <td colSpan={7} className="driver-table__empty">
                  No ranked drivers were returned for this run.
                </td>
              </tr>
            )}
            {drivers.map((d, index) => {
              const amount = Number(d.amount) || 0
              const confidence = Number(d.confidence) || 0
              return (
              <tr key={`${d.account || 'account'}-${d.driver || index}`} onClick={() => openEvidence(d)}>
                <td>
                  <div className="driver-table__account">
                    <span>{d.account || 'Unknown account'}</span>
                    <small>{driverType(d.account)}</small>
                  </div>
                </td>
                <td>{formatPlainCurrency(d.current)}</td>
                <td>{formatPlainCurrency(d.prior)}</td>
                <td className={amount >= 0 ? 'text-up' : 'text-down'}>
                  {formatCurrency(amount)}
                </td>
                <td className={amount >= 0 ? 'text-up' : 'text-down'}>
                  <span className={`change-pill ${amount >= 0 ? 'change-pill--up' : 'change-pill--down'}`}>
                    {d.share_of_change_pct >= 0 ? '+' : ''}
                    {Number(d.share_of_change_pct) || 0}%
                  </span>
                </td>
                <td className="driver-table__driver-name">{d.driver || 'Unknown driver'}</td>
                <td>
                  <span className="confidence-pill">
                    <span style={{ width: `${Math.round(confidence * 100)}%` }} />
                    <b>{Math.round(confidence * 100)}%</b>
                  </span>
                </td>
              </tr>
              )
            })}
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
                          {formatCurrency(tx.amount)}
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

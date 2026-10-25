import { ledgerChange, ledgerMoney, toNumber } from '../../utils/format'
import './DriverTable.css'

function driverType(account) {
  const lowered = String(account || '').toLowerCase()
  if (lowered.includes('refund')) return 'Contra-revenue'
  if (['commission', 'hosting', 'cost', 'ads', 'infrastructure', 'payroll', 'expense', 'marketing'].some((w) => lowered.includes(w))) return 'Spend'
  if (lowered.includes('revenue') || lowered.includes('sales')) return 'Revenue'
  return 'Other account'
}

export default function DriverTable({ drivers = [], onOpenDriver }) {
  return (
    <div className="driver-table-wrap">
      <div className="panel-heading">
        <div>
          <h2>Driver drilldown</h2>
          <p>Select a driver to see the source transactions behind it</p>
        </div>
        <span className="driver-table__count">{drivers.length} drivers, largest first</span>
      </div>

      <div className="driver-table__scroll">
        <table className="driver-table">
          <thead>
            <tr>
              <th scope="col">Driver</th>
              <th scope="col">Account</th>
              <th scope="col" className="num">Prior</th>
              <th scope="col" className="num">Current</th>
              <th scope="col" className="num">Change</th>
              <th scope="col" className="num">% change</th>
              <th scope="col" className="num">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {drivers.length === 0 && (
              <tr>
                <td colSpan={7} className="driver-table__empty">
                  This run found no ranked drivers. Check the Agent run tab for data-quality warnings.
                </td>
              </tr>
            )}
            {drivers.map((d, index) => {
              const amount = toNumber(d.amount)
              const confidence = Math.round(toNumber(d.confidence) * 100)
              const pct = toNumber(d.share_of_change_pct)
              return (
                <tr key={`${d.account || 'account'}-${d.driver || index}`} onClick={() => onOpenDriver?.(d)}>
                  <th scope="row">
                    <button type="button" className="driver-table__open" onClick={(e) => { e.stopPropagation(); onOpenDriver?.(d) }}>
                      {d.driver || 'Unknown driver'}
                    </button>
                  </th>
                  <td>
                    <div className="driver-table__account">
                      <span>{d.account || 'Unknown account'}</span>
                      <small>{driverType(d.account)}</small>
                    </div>
                  </td>
                  <td className="num">{ledgerMoney(d.prior)}</td>
                  <td className="num">{ledgerMoney(d.current)}</td>
                  <td className={`num num--strong ${amount < 0 ? 'text-down' : 'text-up'}`}>{ledgerChange(amount)}</td>
                  <td className={`num ${pct < 0 ? 'text-down' : ''}`}>
                    {pct > 0 ? '+' : ''}{pct}%
                  </td>
                  <td className="num">
                    <span className="confidence">
                      <span className="confidence__track" aria-hidden="true">
                        <span style={{ width: `${confidence}%` }} />
                      </span>
                      {confidence}%
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

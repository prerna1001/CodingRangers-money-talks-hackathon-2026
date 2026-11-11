import { useState } from 'react'
import { fetchDriverEvidence } from '../../services/mockApi'
import WaterfallChart from './WaterfallChart'
import DriverCharts from './DriverCharts'
import DriverTable from './DriverTable'
import EvidenceDrawer from './EvidenceDrawer'

// The Drivers tab. Owns the evidence drawer so every chart bar and every
// table row opens the same "show me the transactions" panel.
export default function DriversView({ waterfall, drivers, periods }) {
  const [openDriver, setOpenDriver] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [loading, setLoading] = useState(false)

  const openEvidence = async (driver) => {
    setOpenDriver(driver)
    setEvidence(null)
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
    <div className="dashboard__drivers-grid">
      <WaterfallChart waterfall={waterfall} drivers={drivers} onSelectDriver={openEvidence} />
      <DriverCharts
        drivers={drivers}
        periods={{ prior: periods.prior.label, current: periods.current.label }}
        onSelectDriver={openEvidence}
      />
      <DriverTable drivers={drivers} onOpenDriver={openEvidence} />
      {openDriver && (
        <EvidenceDrawer driver={openDriver} evidence={evidence} loading={loading} onClose={closeEvidence} />
      )}
    </div>
  )
}

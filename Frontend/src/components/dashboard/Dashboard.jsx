import { useState } from 'react'
import ExecutiveSummary from './ExecutiveSummary'
import WaterfallChart from './WaterfallChart'
import DriverTable from './DriverTable'
import PipelinePanel from './PipelinePanel'
import MemoryPanel from './MemoryPanel'
import RagPanel from './RagPanel'
import StressTestPanel from './StressTestPanel'
import ScenarioSimulator from './ScenarioSimulator'
import ReportPanel from './ReportPanel'
import './Dashboard.css'

const TABS = [
  { id: 'summary', label: 'Summary' },
  { id: 'drivers', label: 'Drivers' },
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'memory', label: 'Memory' },
  { id: 'rag', label: 'RAG evidence' },
  { id: 'stress', label: 'Stress tests' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'report', label: 'Report' },
]

export default function Dashboard({ analysis, onReset }) {
  const [tab, setTab] = useState('summary')

  const revenueChangePct = Math.round(
    ((analysis.periods.current.revenue - analysis.periods.prior.revenue) / analysis.periods.prior.revenue) * 100,
  )

  return (
    <div className="dashboard">
      <div className="dashboard__toolbar">
        <nav className="dashboard__tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`dashboard__tab ${tab === t.id ? 'dashboard__tab--active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onReset}>
          New analysis
        </button>
      </div>

      <div className="dashboard__panel">
        {tab === 'summary' && <ExecutiveSummary analysis={analysis} />}
        {tab === 'drivers' && (
          <>
            <WaterfallChart waterfall={analysis.waterfall} />
            <div className="dashboard__spacer" />
            <DriverTable drivers={analysis.drivers} />
          </>
        )}
        {tab === 'pipeline' && <PipelinePanel steps={analysis.agent_timeline} />}
        {tab === 'memory' && <MemoryPanel />}
        {tab === 'rag' && <RagPanel />}
        {tab === 'stress' && <StressTestPanel />}
        {tab === 'scenarios' && <ScenarioSimulator baselinePct={revenueChangePct} />}
        {tab === 'report' && <ReportPanel analysis={analysis} />}
      </div>
    </div>
  )
}

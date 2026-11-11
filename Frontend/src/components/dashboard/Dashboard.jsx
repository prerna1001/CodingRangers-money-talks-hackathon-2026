import { useRef, useState } from 'react'
import ExecutiveSummary from './ExecutiveSummary'
import WaterfallChart from './WaterfallChart'
import DriverTable from './DriverTable'
import PipelinePanel from './PipelinePanel'
import MemoryPanel from './MemoryPanel'
import RagPanel from './RagPanel'
import StressTestPanel from './StressTestPanel'
import ScenarioSimulator from './ScenarioSimulator'
import ReportPanel from './ReportPanel'
import ChatPanel from './ChatPanel'
import { useLanguage } from '../../i18n/context'
import TabVoiceButton from './TabVoiceButton'
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
  const { t } = useLanguage()
  const [tab, setTab] = useState('summary')
  const [chatOpen, setChatOpen] = useState(false)
  const panelRef = useRef(null)
  const periods = analysis?.periods ?? {}
  const prior = periods.prior ?? { label: 'Prior', revenue: 0 }
  const current = periods.current ?? { label: 'Current', revenue: 0 }
  const drivers = Array.isArray(analysis?.drivers) ? analysis.drivers : []
  const waterfall = Array.isArray(analysis?.waterfall) ? analysis.waterfall : []
  const agentTimeline = Array.isArray(analysis?.agent_timeline) ? analysis.agent_timeline : []

  const priorRevenue = Number(prior.revenue) || 0
  const currentRevenue = Number(current.revenue) || 0
  const revenueChangePct = priorRevenue
    ? Math.round(((currentRevenue - priorRevenue) / priorRevenue) * 100)
    : 0
  const normalizedAnalysis = {
    ...analysis,
    periods: { prior, current },
    drivers,
    waterfall,
    agent_timeline: agentTimeline,
  }

  return (
    <div className={`dashboard ${chatOpen ? 'dashboard--chat-open' : ''}`}>
      <div className="dashboard__toolbar">
        <nav className="dashboard__tabs">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`dashboard__tab ${tab === item.id ? 'dashboard__tab--active' : ''}`}
              onClick={() => setTab(item.id)}
            >
              {t(item.label)}
            </button>
          ))}
        </nav>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onReset}>
          {t('New analysis')}
        </button>
        <TabVoiceButton targetRef={panelRef} />
      </div>

      <div className="dashboard__panel" ref={panelRef}>
        {tab === 'summary' && <ExecutiveSummary analysis={normalizedAnalysis} />}
        {tab === 'drivers' && (
          <div className="dashboard__drivers-grid">
            <WaterfallChart waterfall={waterfall} drivers={drivers} />
            <DriverTable drivers={drivers} />
          </div>
        )}
        {tab === 'pipeline' && <PipelinePanel steps={agentTimeline} analysis={normalizedAnalysis} />}
        {tab === 'memory' && <MemoryPanel />}
        {tab === 'rag' && <RagPanel />}
        {tab === 'stress' && <StressTestPanel />}
        {tab === 'scenarios' && <ScenarioSimulator baselinePct={revenueChangePct} />}
        {tab === 'report' && <ReportPanel analysis={normalizedAnalysis} />}
      </div>

      {chatOpen && (
        <>
          <button
            type="button"
            className="dashboard__chat-scrim"
            onClick={() => setChatOpen(false)}
            aria-label={t('Close chatbot')}
          />
          <aside className="dashboard__chat-drawer" aria-label={t('Chatbot')}>
          <button
            type="button"
            className="dashboard__chat-close"
            onClick={() => setChatOpen(false)}
            aria-label={t('Close chatbot')}
            title={t('Close chatbot')}
          >
            ×
          </button>
          <ChatPanel analysis={normalizedAnalysis} compact />
        </aside>
        </>
      )}
      <button
        type="button"
        className="dashboard__chat-launcher"
        onClick={() => setChatOpen((open) => !open)}
        aria-label={chatOpen ? t('Close chatbot') : t('Open chatbot')}
        aria-expanded={chatOpen}
        title={chatOpen ? t('Close chatbot') : t('Open chatbot')}
      >
        {chatOpen ? '×' : '💬'}
      </button>
    </div>
  )
}

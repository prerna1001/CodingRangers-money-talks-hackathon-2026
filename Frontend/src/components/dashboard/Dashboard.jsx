import { lazy, Suspense, useRef, useState } from 'react'
import ExecutiveSummary from './ExecutiveSummary'
import PipelinePanel from './PipelinePanel'
import MemoryPanel from './MemoryPanel'
import RagPanel from './RagPanel'
import StressTestPanel from './StressTestPanel'
import ScenarioSimulator from './ScenarioSimulator'
import ReportPanel from './ReportPanel'
import ChatPanel from './ChatPanel'
import TabVoiceButton from './TabVoiceButton'
import { useLanguage } from '../../i18n/context'
import Icon from '../Icon'
import './Dashboard.css'

const DriversView = lazy(() => import('./DriversView'))

const TABS = [
  { id: 'summary', label: 'Summary' },
  { id: 'drivers', label: 'Drivers' },
  { id: 'pipeline', label: 'Agent run' },
  { id: 'memory', label: 'Memory' },
  { id: 'rag', label: 'Retrieved context' },
  { id: 'stress', label: 'Stress tests' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'report', label: 'Report' },
]

export default function Dashboard({ analysis, onReset }) {
  const { t } = useLanguage()
  const [tab, setTab] = useState('summary')
  const [chatOpen, setChatOpen] = useState(false)
  const panelRef = useRef(null)
  const tabRefs = useRef({})
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

  // Arrow keys move between tabs (WAI-ARIA tabs pattern); Tab moves into the panel.
  const handleTabKey = (event) => {
    const index = TABS.findIndex((item) => item.id === tab)
    let next = null
    if (event.key === 'ArrowRight') next = TABS[(index + 1) % TABS.length]
    if (event.key === 'ArrowLeft') next = TABS[(index - 1 + TABS.length) % TABS.length]
    if (event.key === 'Home') next = TABS[0]
    if (event.key === 'End') next = TABS[TABS.length - 1]
    if (!next) return
    event.preventDefault()
    setTab(next.id)
    tabRefs.current[next.id]?.focus()
  }

  return (
    <div className="dashboard">
      <div className="dashboard__masthead">
        <h1 className="dashboard__title">
          {prior.label} <span className="dashboard__to">{t('to')}</span> {current.label}
        </h1>
        <div className="dashboard__actions">
          <TabVoiceButton targetRef={panelRef} />
          <button type="button" className="btn btn--ghost btn--sm" onClick={onReset}>
            {t('New analysis')}
          </button>
        </div>
      </div>

      <div className="dashboard__tabs" role="tablist" aria-label={t('Analysis views')} onKeyDown={handleTabKey}>
        {TABS.map((item) => (
          <button
            key={item.id}
            ref={(node) => { tabRefs.current[item.id] = node }}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`panel-${item.id}`}
            tabIndex={tab === item.id ? 0 : -1}
            className={`dashboard__tab ${tab === item.id ? 'dashboard__tab--active' : ''}`}
            onClick={() => setTab(item.id)}
          >
            {t(item.label)}
          </button>
        ))}
      </div>

      <div
        className={`dashboard__panel dashboard__panel--${tab}`}
        role="tabpanel"
        id={`panel-${tab}`}
        ref={panelRef}
        aria-labelledby={`tab-${tab}`}
      >
        {tab === 'summary' && <ExecutiveSummary analysis={normalizedAnalysis} />}
        {tab === 'drivers' && (
          <Suspense fallback={<p className="panel-loading">Loading charts…</p>}>
            <DriversView waterfall={waterfall} drivers={drivers} periods={{ prior, current }} />
          </Suspense>
        )}
        {tab === 'pipeline' && <PipelinePanel steps={agentTimeline} />}
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
              <Icon name="close" />
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
        <Icon name={chatOpen ? 'close' : 'chat'} />
      </button>
    </div>
  )
}

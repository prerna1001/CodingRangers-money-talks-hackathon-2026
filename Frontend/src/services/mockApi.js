// Dummy implementations for every endpoint in HACKATHON_PLAN.original.md that
// has no backend route yet (memory, RAG evidence, stress tests, voice, report,
// evidence drilldown). Each function is named and shaped after its real
// endpoint (see constants/api.js) and returns a Promise, so a call site never
// changes when a mock is later replaced by a real fetch().
import { API_ENDPOINTS } from '../constants/api'
import {
  MOCK_MEMORIES,
  MOCK_RAG_EVIDENCE,
  MOCK_STRESS_TESTS,
  mockEvidenceForDriver,
} from '../data/mockData'

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export async function fetchMemories() {
  await delay(300)
  return { url: API_ENDPOINTS.memory, method: 'GET', memories: MOCK_MEMORIES }
}

export async function deleteMemory(memoryId) {
  await delay(250)
  return { url: API_ENDPOINTS.memoryDelete(memoryId), method: 'DELETE', status: 'deleted', memory_id: memoryId }
}

export async function fetchRagEvidence() {
  await delay(350)
  return { url: API_ENDPOINTS.runEvidence('current'), method: 'GET', evidence: MOCK_RAG_EVIDENCE }
}

export async function fetchDriverEvidence(driverName) {
  await delay(250)
  return {
    url: API_ENDPOINTS.runEvidence('current'),
    method: 'GET',
    driver: driverName,
    transactions: mockEvidenceForDriver(driverName),
  }
}

export async function runStressTests() {
  await delay(1100)
  return { url: API_ENDPOINTS.stressTestsRun, method: 'POST', checks: MOCK_STRESS_TESTS }
}

export async function generateVoiceBriefing(runId, headline) {
  await delay(1400)
  return {
    url: API_ENDPOINTS.voice(runId),
    method: 'POST',
    status: 'ready',
    duration_sec: 52,
    script: `${headline} Three customers accounted for nearly two-thirds of the increase. Expenses also rose, mainly due to hosting and commissions. Customer concentration and services revenue deserve follow-up.`,
  }
}

export async function runScenario(scenarioId, baseline) {
  await delay(500)
  const scenarios = {
    remove_top_customer: {
      label: 'What if Northwind Labs had not expanded?',
      adjusted_change_pct: 8,
      note: 'Removing the largest single driver drops MoM growth from 18% to roughly 8%.',
    },
    normalize_refunds: {
      label: 'What if refunds were normalized to trailing average?',
      adjusted_change_pct: 16,
      note: 'Minimal impact — this dataset has no material refund volatility this period.',
    },
    exclude_onetime: {
      label: 'What if we exclude one-time services engagements?',
      adjusted_change_pct: 21,
      note: 'Excluding the professional-services dip makes growth look stronger, 21% vs 18%.',
    },
  }
  return { scenario_id: scenarioId, baseline_pct: baseline, ...scenarios[scenarioId] }
}

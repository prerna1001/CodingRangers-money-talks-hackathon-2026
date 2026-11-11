// Full endpoint list from HACKATHON_PLAN.original.md ("API Endpoints").
// `upload` and `analyze` are wired to the real FastAPI backend (backend/main.py).
// Everything else here has no backend route yet — services/mockApi.js resolves
// them locally, but keeps the same URL string so swapping a mock function for a
// real fetch() later is the only change needed, at that one call site.
export const API_ENDPOINTS = {
  upload: '/api/upload',
  analyze: '/api/analyze',
  chat: '/api/chat',
  voiceSpeak: '/api/voice/speak',
  voiceTranscribe: '/api/voice/transcribe',
  analyzeStream: (runId) => `/api/analyze/stream/${runId}`,
  runs: '/api/runs',
  run: (runId) => `/api/runs/${runId}`,
  runEvidence: (runId) => `/api/runs/${runId}/evidence`,
  memory: '/api/memory',
  memoryDelete: (memoryId) => `/api/memory/${memoryId}`,
  stressTestsRun: '/api/stress-tests/run',
  reportPdf: (runId) => `/api/reports/${runId}/pdf`,
  voice: (runId) => `/api/voice/${runId}`,
  translate: '/api/translate',
  translateLanguages: '/api/translate/languages',
}

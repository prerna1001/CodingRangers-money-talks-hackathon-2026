// Canned data for dashboard panels that have no backend yet. Shapes follow
// the examples given in HACKATHON_PLAN.original.md so swapping in real data
// later doesn't require touching the components that render it.

export const MOCK_MEMORIES = [
  {
    memory_id: 'mem_001',
    memory_type: 'business_pattern',
    content: 'Enterprise renewals usually spike in the last month of each quarter.',
    evidence: ['2026-03 analysis', '2026-06 analysis'],
    confidence: 0.82,
    used_in_this_run: true,
  },
  {
    memory_id: 'mem_002',
    memory_type: 'recurring_vendor',
    content: 'AWS, "Amazon Web Services", and "AMZN AWS" all refer to the same vendor.',
    evidence: ['2026-05 analysis'],
    confidence: 0.95,
    used_in_this_run: true,
  },
  {
    memory_id: 'mem_003',
    memory_type: 'user_correction',
    content: 'User confirmed Meridian Health is an enterprise account, not mid-market.',
    evidence: ['user correction on 2026-07 run'],
    confidence: 1.0,
    used_in_this_run: false,
  },
]

export const MOCK_RAG_EVIDENCE = [
  {
    source: 'Previous analysis report',
    title: '2026-07 Monthly Explanation',
    snippet: 'Revenue grew 9% driven by SMB renewals; enterprise pipeline was flagged as a Q3 opportunity.',
    relevance: 0.88,
  },
  {
    source: 'Chart of accounts',
    title: 'Subscription revenue definition',
    snippet: 'Subscription revenue includes SMB, Enterprise, and Professional Services subscription lines.',
    relevance: 0.74,
  },
  {
    source: 'Customer segmentation notes',
    title: 'Enterprise tier definition',
    snippet: 'Enterprise = contracts >$50k ACV. Northwind Labs, AtlasGrid, and Meridian Health are all Enterprise tier.',
    relevance: 0.91,
  },
  {
    source: 'Accounting policy notes',
    title: 'Revenue recognition policy',
    snippet: 'Subscription revenue is recognized monthly on a straight-line basis over the contract term.',
    relevance: 0.62,
  },
]

export const MOCK_STRESS_TESTS = [
  { name: 'Prompt injection in CSV memo', status: 'pass', detail: 'Injection string ignored; not reflected in output.' },
  { name: 'Duplicate transactions', status: 'pass', detail: '3 duplicate rows detected and excluded from totals.' },
  { name: 'Missing customer names', status: 'warn', detail: '12 transactions missing customer_name.' },
  { name: 'Summary vs. transaction reconciliation', status: 'pass', detail: 'Difference of $250 (0.14%), within threshold.' },
  { name: 'Vendor name inconsistency', status: 'warn', detail: '"AWS" / "Amazon Web Services" merged via memory.' },
  { name: 'Outlier transaction robustness', status: 'pass', detail: 'One 100x-normal transaction flagged, excluded from trend calc.' },
  { name: 'Hallucination check', status: 'pass', detail: 'Every numeric claim traced to source transactions.' },
]

export function mockEvidenceForDriver(driverName) {
  const base = [
    { date: '2026-08-04', customer: 'Northwind Labs', amount: 18000, category: 'Enterprise subscription', memo: 'Expansion — added 40 seats' },
    { date: '2026-08-11', customer: 'AtlasGrid', amount: 14000, category: 'Enterprise subscription', memo: 'Upsell — annual to multi-year' },
    { date: '2026-08-19', customer: 'Meridian Health', amount: 10000, category: 'Enterprise subscription', memo: 'New enterprise contract' },
  ]
  const churn = [
    { date: '2026-08-02', customer: 'Fernwood Retail', amount: -2400, category: 'SMB subscription', memo: 'Cancellation — budget cuts' },
    { date: '2026-08-09', customer: 'Bluepeak Co', amount: -1800, category: 'SMB subscription', memo: 'Cancellation — non-renewal' },
  ]
  const services = [
    { date: '2026-08-06', customer: 'Vantree Inc', amount: -2500, category: 'Professional services', memo: 'Onboarding engagement completed, no repeat' },
    { date: '2026-08-21', customer: 'Coastal Analytics', amount: -2500, category: 'Professional services', memo: 'Scope reduced from prior month' },
  ]
  if (driverName.toLowerCase().includes('churn')) return churn
  if (driverName.toLowerCase().includes('service')) return services
  return base
}

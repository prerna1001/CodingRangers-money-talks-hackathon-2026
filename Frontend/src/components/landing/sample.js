// Everything the landing page shows comes from the sample dataset that ships
// with the repository (test_data/01_saas_clean), so no figure here is made up.
// The prior/current amounts are the July and August transactions per customer.

function txn(id, date, amount, memo) {
  return { id, date, amount, memo }
}

function line(name, before, after) {
  return { name, before, after, change: after.amount - before.amount }
}

export const SAMPLE = {
  account: 'Subscription revenue',
  prior: { label: '2026-07', revenue: 155000 },
  current: { label: '2026-08', revenue: 183000 },
  summary: [
    { account: 'Subscription revenue', prior: 155000, current: 183000 },
    { account: 'Cloud hosting', prior: 29100, current: 35500 },
  ],
  lines: [
    line(
      'Northwind Labs',
      txn('jul_northwind', '2026-07-14', 22000, 'Base subscription'),
      txn('aug_northwind', '2026-08-14', 40000, 'Expansion: 40 seats added'),
    ),
    line(
      'AtlasGrid',
      txn('jul_atlas', '2026-07-18', 18000, 'Base subscription'),
      txn('aug_atlas', '2026-08-18', 32000, 'Expansion: additional seats'),
    ),
    line(
      'SMB Bulk',
      txn('jul_smb', '2026-07-05', 100000, 'Aggregated SMB subscriptions'),
      txn('aug_smb', '2026-08-05', 86000, 'Aggregated SMB subscriptions'),
    ),
    line(
      'Meridian Health',
      txn('jul_meridian', '2026-07-22', 15000, 'Base subscription'),
      txn('aug_meridian', '2026-08-22', 25000, 'Expansion: additional seats'),
    ),
  ],
}

// The pipeline stages, in the order the app runs them (README, "Agentic workflow").
export const SAMPLE_CHECKS = [
  { name: 'Profile Builder', does: 'Reads the files and the business context' },
  { name: 'Data QA', does: 'Gates the run on data quality' },
  { name: 'Memory', does: 'Recalls what earlier runs found' },
  { name: 'RAG', does: 'Retrieves supporting context' },
  { name: 'Analyst', does: 'Explains the facts the engine computed' },
  { name: 'Guardrail', does: 'Sends back anything the data does not support' },
  { name: 'Stress Test', does: 'Tries duplicates, injected text and outliers' },
  { name: 'Report Writer', does: 'Writes the report from approved claims only' },
]

// Extensions the upload form accepts (UploadCard ACCEPTED_FORMATS).
export const SAMPLE_FORMATS = [
  { kind: 'Spreadsheets', types: 'CSV  XLSX' },
  { kind: 'Documents', types: 'PDF  DOCX  TXT  JSON' },
  { kind: 'Photos of statements', types: 'JPEG  PNG  WEBP  TIFF  HEIC' },
]

// The assistant's rule-based reply for the sample run (backend api/routes/chat.py).
export const SAMPLE_ANSWER = {
  en: {
    question: 'Why did revenue increase?',
    reply:
      'The biggest driver is Northwind Labs in Subscription revenue, moving $18,000 ($22,000 to $40,000). Next largest: AtlasGrid ($14,000), SMB Bulk (-$14,000).',
    meta: 'Answered from this run’s figures',
  },
  es: {
    question: '¿Por qué aumentaron los ingresos?',
    reply:
      'El factor principal es Northwind Labs en ingresos por suscripción, con un cambio de $18,000 ($22,000 a $40,000). Le siguen AtlasGrid ($14,000) y SMB Bulk (-$14,000).',
    meta: 'Respondido con las cifras de este análisis',
  },
}

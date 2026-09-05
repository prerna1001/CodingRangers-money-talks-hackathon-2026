// Diagnostic: render the real dashboard components against a real API
// payload through Vite's SSR pipeline, to find render-time crashes that
// would otherwise show up in the browser only as a blank screen.
import { createServer } from 'vite'
import { renderToString } from 'react-dom/server'
import React from 'react'

const payload = JSON.parse(process.argv[2])

const vite = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
})

async function check(name, path, props) {
  try {
    const mod = await vite.ssrLoadModule(path)
    const html = renderToString(React.createElement(mod.default, props))
    console.log(`  OK    ${name} (${html.length} chars)`)
  } catch (err) {
    console.log(`  CRASH ${name}: ${err.message}`)
    if (err.stack) console.log(err.stack.split('\n').slice(1, 4).join('\n'))
  }
}

console.log('rendering with real payload:')
await check('ExecutiveSummary', '/src/components/dashboard/ExecutiveSummary.jsx', { analysis: payload })
await check('WaterfallChart', '/src/components/dashboard/WaterfallChart.jsx', { waterfall: payload.waterfall })
await check('DriverTable', '/src/components/dashboard/DriverTable.jsx', { drivers: payload.drivers })
await check('PipelinePanel', '/src/components/dashboard/PipelinePanel.jsx', { steps: payload.agent_timeline })
await check('ReportPanel', '/src/components/dashboard/ReportPanel.jsx', { analysis: payload })
await check('Dashboard', '/src/components/dashboard/Dashboard.jsx', { analysis: payload, onReset: () => {} })

await vite.close()

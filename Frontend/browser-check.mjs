// Diagnostic: drive the real dashboard in a real browser against the real
// backend, capturing console output, page errors, failed requests, and the
// visible phase — so a blank/stuck screen becomes an actual error message.
import { chromium } from 'playwright-core'

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const CSVS = process.argv.slice(2)

const browser = await chromium.launch({ executablePath: EDGE, headless: true })
const page = await browser.newPage()

page.on('console', (m) => console.log(`  [console.${m.type()}] ${m.text().slice(0, 300)}`))
page.on('pageerror', (e) => console.log(`  [PAGE ERROR] ${e.message}`))
page.on('requestfailed', (r) => console.log(`  [REQ FAILED] ${r.url()} ${r.failure()?.errorText}`))
page.on('response', (r) => {
  if (r.url().includes('/api/')) console.log(`  [api] ${r.status()} ${r.url().replace('http://localhost:5173', '')}`)
})

console.log('1. loading app...')
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
console.log('   title:', await page.title())

console.log('2. uploading', CSVS.join(', '))
await page.setInputFiles('input[type=file]', CSVS)
await page.getByRole('button', { name: /upload/i }).first().click()

console.log('3. waiting for upload to succeed...')
await page.getByRole('button', { name: /run analysis|analyze/i }).first().waitFor({ timeout: 30000 })
await page.getByRole('button', { name: /run analysis|analyze/i }).first().click()

console.log('4. waiting for dashboard (up to 150s)...')
try {
  await page.waitForSelector('.dashboard', { timeout: 150000 })
  console.log('   ✅ DASHBOARD RENDERED')
  const headline = await page.locator('.exec-summary__headline').first().textContent().catch(() => null)
  console.log('   headline:', headline)
} catch {
  console.log('   ❌ dashboard never appeared')
  const phase = await page.evaluate(() => {
    const t = document.querySelector('.agent-timeline h2')?.textContent
    const pct = document.querySelector('.agent-timeline__pct')?.textContent
    const err = document.querySelector('.banner--error')?.textContent
    return { timelineHeading: t, progress: pct, error: err, bodyLen: document.body.innerHTML.length }
  })
  console.log('   visible state:', JSON.stringify(phase))
}

await browser.close()

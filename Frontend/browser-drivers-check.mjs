import { chromium } from 'playwright-core'

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const CSV = process.argv[2] || '../test_data/02_ecommerce_clean/transactions.csv'
const OUT = process.argv[3] || '../drivers-tab-check.png'

const browser = await chromium.launch({ executablePath: EDGE, headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })

page.on('pageerror', (e) => console.log(`  [PAGE ERROR] ${e.message}`))
page.on('requestfailed', (r) => {
  if (!r.url().includes('fonts.googleapis.com')) {
    console.log(`  [REQ FAILED] ${r.url()} ${r.failure()?.errorText}`)
  }
})

console.log('1. loading app')
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })

console.log('2. uploading sample CSV')
await page.setInputFiles('input[type=file]', CSV)
await page.getByRole('button', { name: /^upload$/i }).click()
await page.getByRole('button', { name: /run analysis/i }).waitFor({ timeout: 30000 })
await page.getByRole('button', { name: /run analysis/i }).click()

console.log('3. waiting for dashboard')
await page.waitForSelector('.dashboard', { timeout: 180000 })
await page.getByRole('button', { name: 'Drivers' }).click()
await page.waitForSelector('.waterfall-chart__svg')
await page.waitForSelector('.driver-table tbody tr')

const checks = await page.evaluate(() => {
  const chart = document.querySelector('.waterfall-chart__svg')?.getBoundingClientRect()
  const rows = [...document.querySelectorAll('.driver-table tbody tr')]
  const labels = [...document.querySelectorAll('.waterfall-chart__label')].map((node) => node.textContent)
  const values = [...document.querySelectorAll('.waterfall-chart__value')].map((node) => node.textContent)
  return {
    chartWidth: Math.round(chart?.width || 0),
    chartHeight: Math.round(chart?.height || 0),
    rowCount: rows.length,
    labels,
    values,
  }
})

await page.screenshot({ path: OUT, fullPage: true })
console.log('4. screenshot:', OUT)
console.log('5. checks:', JSON.stringify(checks))

await browser.close()

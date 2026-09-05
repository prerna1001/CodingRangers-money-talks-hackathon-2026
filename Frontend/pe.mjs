import { chromium } from 'playwright-core'
const b = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true })
const p = await b.newPage()
p.on('pageerror', e => console.log('PAGE ERROR:', e.message))
p.on('console', m => { if (m.type()==='error') console.log('CONSOLE ERROR:', m.text().slice(0,400)) })
await p.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
console.log('has input:', await p.locator('input[type=file]').count())
console.log('body:', (await p.locator('body').innerText()).slice(0,200))
await b.close()

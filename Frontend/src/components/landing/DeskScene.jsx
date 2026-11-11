import { useEffect, useRef } from 'react'
import Tick from '../Tick'
import { ledgerChange, ledgerMoney } from '../../utils/format'
import { SAMPLE } from './sample'
import './DeskScene.css'

// The job played as paperwork on a desk, in CSS 3D: a period summary, the
// transaction slips it was built from, and the bridge that explains the
// change. It assembles once, then only leans a little toward the pointer.
export default function DeskScene() {
  const sceneRef = useRef(null)

  useEffect(() => {
    const scene = sceneRef.current
    if (!scene || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined
    if (!window.matchMedia('(pointer: fine)').matches) return undefined

    let frame = 0
    const onMove = (event) => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const rect = scene.getBoundingClientRect()
        const x = (event.clientX - rect.left) / rect.width - 0.5
        const y = (event.clientY - rect.top) / rect.height - 0.5
        scene.style.setProperty('--lean-x', `${(-y * 5).toFixed(2)}deg`)
        scene.style.setProperty('--lean-z', `${(x * 6).toFixed(2)}deg`)
      })
    }
    const onLeave = () => {
      scene.style.setProperty('--lean-x', '0deg')
      scene.style.setProperty('--lean-z', '0deg')
    }
    scene.addEventListener('pointermove', onMove)
    scene.addEventListener('pointerleave', onLeave)
    return () => {
      cancelAnimationFrame(frame)
      scene.removeEventListener('pointermove', onMove)
      scene.removeEventListener('pointerleave', onLeave)
    }
  }, [])

  const slips = SAMPLE.lines.map((line) => line.after)

  return (
    <figure className="desk-scene" ref={sceneRef}>
      <div className="desk-scene__plane">
        <div className="desk-sheet desk-sheet--summary stock">
          <p className="sheet__title">Period summary</p>
          <div className="desk-sheet__cols desk-sheet__cols--head">
            <span />
            <span>{SAMPLE.prior.label}</span>
            <span>{SAMPLE.current.label}</span>
          </div>
          {SAMPLE.summary.map((row) => (
            <div className="desk-sheet__cols" key={row.account}>
              <span>{row.account}</span>
              <span className="fig">{ledgerMoney(row.prior)}</span>
              <span className="fig">{ledgerMoney(row.current)}</span>
            </div>
          ))}
        </div>

        <div className="desk-stack" aria-hidden="true">
          {slips.map((slip, index) => (
            <div className="desk-slip stock" key={slip.id} style={{ '--i': index }}>
              <span className="fig">{slip.date}</span>
              <span className="fig desk-slip__amount">{ledgerMoney(slip.amount)}</span>
              <span className="desk-slip__memo">{slip.memo}</span>
            </div>
          ))}
        </div>

        <div className="desk-sheet desk-sheet--bridge stock">
          <p className="sheet__title">Revenue bridge</p>
          <div className="sheet__row sheet__row--balance">
            <span>{SAMPLE.prior.label} revenue</span>
            <span className="fig">{ledgerMoney(SAMPLE.prior.revenue)}</span>
          </div>
          {SAMPLE.lines.map((line, index) => (
            <div className="sheet__row desk-line" key={line.name} style={{ '--i': index }}>
              <span>{line.name}</span>
              <span className={`fig ${line.change < 0 ? 'text-down' : ''}`}>{ledgerChange(line.change)}</span>
              <Tick style={{ '--i': index }} />
            </div>
          ))}
          <div className="sheet__row sheet__row--total">
            <span>{SAMPLE.current.label} revenue</span>
            <span className="fig">{ledgerMoney(SAMPLE.current.revenue)}</span>
          </div>
          <p className="desk-stamp">Verified</p>
        </div>
      </div>
      <figcaption className="visually-hidden">
        A period summary, a stack of transaction slips, and the revenue bridge built from them: {SAMPLE.prior.label} revenue {ledgerMoney(SAMPLE.prior.revenue)}, {SAMPLE.current.label} revenue {ledgerMoney(SAMPLE.current.revenue)}.
      </figcaption>
    </figure>
  )
}

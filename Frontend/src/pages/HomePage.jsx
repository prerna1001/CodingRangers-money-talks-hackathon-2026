import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { AuthCheck } from '../auth/AuthProvider'
import { useAuth } from '../auth/authContext'
import Tick from '../components/Tick'
import DeskScene from '../components/landing/DeskScene'
import { ledgerChange, ledgerMoney } from '../utils/format'
import { SAMPLE, SAMPLE_ANSWER, SAMPLE_CHECKS, SAMPLE_FORMATS } from '../components/landing/sample'
import './HomePage.css'

// Adds .is-seen the first time a section scrolls into view. Sections are
// visible by default; the class only starts the one-off motion inside them.
function useSeen() {
  const ref = useRef(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const node = ref.current
    if (!node || typeof IntersectionObserver === 'undefined') {
      setSeen(true)
      return undefined
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true)
          observer.disconnect()
        }
      },
      { threshold: 0.25 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, seen]
}

// The bridge sheet doubles as a control: pick a line, see its transactions.
function TraceSection() {
  const [selected, setSelected] = useState(0)
  const [ref, seen] = useSeen()
  const line = SAMPLE.lines[selected]

  return (
    <section className={`trace ${seen ? 'is-seen' : ''}`} ref={ref} aria-labelledby="trace-title">
      <div className="home__container trace__grid">
        <div className="trace__head">
          <h2 id="trace-title">Pick a line. See the transactions behind it.</h2>
          <p className="lead">Each line of the bridge is computed from your source rows, not written by the model.</p>
        </div>

        <div className="trace__sheet stock">
          <p className="sheet__title">Revenue bridge</p>
          <div className="sheet__row sheet__row--balance">
            <span>{SAMPLE.prior.label} revenue</span>
            <span className="fig">{ledgerMoney(SAMPLE.prior.revenue)}</span>
          </div>
          <div className="trace__lines" role="group" aria-label="Bridge lines">
            {SAMPLE.lines.map((item, index) => (
              <button
                key={item.name}
                type="button"
                className={`trace__line ${index === selected ? 'trace__line--on' : ''}`}
                aria-pressed={index === selected}
                onClick={() => setSelected(index)}
                style={{ '--i': index }}
              >
                <span>{item.name}</span>
                <span className={`fig ${item.change < 0 ? 'text-down' : ''}`}>{ledgerChange(item.change)}</span>
                <Tick style={{ '--i': index }} />
              </button>
            ))}
          </div>
          <div className="sheet__row sheet__row--total">
            <span>{SAMPLE.current.label} revenue</span>
            <span className="fig">{ledgerMoney(SAMPLE.current.revenue)}</span>
          </div>
        </div>

        <div className="trace__slips" aria-live="polite">
          <p className="trace__slips-title">{line.name}, {SAMPLE.account}</p>
          {/* key remounts the pair so the slips are dealt again on each pick */}
          <div className="trace__pair" key={line.name}>
            {[line.before, line.after].map((txn, index) => (
              <div className="slip stock" key={txn.id} style={{ '--i': index }}>
                <div className="slip__top">
                  <span className="fig">{txn.date}</span>
                  <span className="fig">{txn.id}</span>
                </div>
                <p className="slip__amount fig">{ledgerMoney(txn.amount)}</p>
                <p className="slip__memo">{txn.memo}</p>
              </div>
            ))}
          </div>
          <p className="trace__result">
            <span className={`fig ${line.change < 0 ? 'text-down' : 'text-up'}`}>{ledgerChange(line.change)}</span>
            {' '}between the two periods
          </p>
        </div>
      </div>
    </section>
  )
}

function ChecksSection() {
  const [ref, seen] = useSeen()
  return (
    <section className={`checks ${seen ? 'is-seen' : ''}`} ref={ref} aria-labelledby="checks-title">
      <div className="home__container checks__grid">
        <h2 id="checks-title">Eight checks run before you read a word.</h2>
        <ol className="checks__list">
          {SAMPLE_CHECKS.map((check, index) => (
            <li key={check.name} style={{ '--i': index }}>
              <span className="fig checks__no">{String(index + 1).padStart(2, '0')}</span>
              <span className="checks__name">{check.name}</span>
              <span className="checks__does">{check.does}</span>
              <Tick style={{ '--i': index }} />
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function AskSection() {
  const [language, setLanguage] = useState('en')
  const answer = SAMPLE_ANSWER[language]
  return (
    <section className="ask" aria-labelledby="ask-title">
      <div className="home__container ask__grid">
        <div className="ask__head">
          <h2 id="ask-title">Ask about the run out loud.</h2>
          <p className="lead">Speak or type a question. The answer uses only this run’s figures, and can be read back to you.</p>
          <div className="groove" role="group" aria-label="Answer language">
            {[['en', 'English'], ['es', 'Español']].map(([code, label]) => (
              <button
                key={code}
                type="button"
                className={`groove__stop ${language === code ? 'groove__stop--on' : ''}`}
                aria-pressed={language === code}
                onClick={() => setLanguage(code)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="ask__thread" lang={language}>
          <p className="ask__q">{answer.question}</p>
          <div className="ask__a stock" key={language}>
            <p>{answer.reply}</p>
            <p className="ask__meta">{answer.meta}</p>
          </div>
        </div>
      </div>
    </section>
  )
}

// Public landing page: reachable signed in or not, never redirects on its
// own. Every "Navigate to app" goes through /signin for visitors not signed in.
export default function HomePage() {
  const { auth, error } = useAuth()

  if (!auth) {
    return <AuthCheck error={error} />
  }

  // Signed-in visitors go straight to the app; everyone else goes through
  // the sign-in page, which holds Log in and Sign up.
  const appPath = auth.authenticated ? '/app' : '/signin'
  const action = (className) => (
    <Link className={className} to={appPath}>
      Navigate to app
    </Link>
  )

  return (
    <div className="page home">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="page__header home__nav">
        <div className="brand">
          <span className="brand__mark"><Tick /></span>
          <span className="brand__name">Ledgerlight</span>
        </div>
        {action('btn btn--sm home__nav-action')}
      </header>

      <main id="main" tabIndex={-1} className="home__main">
        <section className="hero desk" aria-labelledby="hero-title">
          <div className="home__container hero__grid">
            <div className="hero__copy">
              <h1 id="hero-title">Every variance, traced to its transactions.</h1>
              <p className="lead">
                Upload two periods and get an evidence-backed explanation of your numbers.
              </p>
              <div className="hero__actions">{action('btn btn--primary btn--lg home__cta')}</div>
            </div>
            <DeskScene />
          </div>
        </section>

        <TraceSection />
        <ChecksSection />
        <AskSection />

        <section className="formats" aria-labelledby="formats-title">
          <div className="home__container formats__grid">
            <h2 id="formats-title">Bring the files as they are.</h2>
            <dl className="formats__list">
              {SAMPLE_FORMATS.map((group) => (
                <div key={group.kind}>
                  <dt>{group.kind}</dt>
                  <dd className="fig">{group.types}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className="close desk" aria-labelledby="close-title">
          <div className="home__container close__grid">
            <h2 id="close-title">Start with two periods.</h2>
            {action('btn btn--primary btn--lg')}
          </div>
        </section>
      </main>

      <footer className="home__footer">
        <div className="home__container home__footer-grid">
          <p className="home__signoff">Ledgerlight</p>
          <p>Built by Coding Rangers for the Money Talks hackathon, 2026.</p>
          <p>Figures on this page come from the sample SaaS dataset in the repository.</p>
        </div>
      </footer>
    </div>
  )
}

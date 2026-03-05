'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useCursor } from './js/cursor';
import { useLiveStats, useLiveFeed } from './js/live';

const REVEAL_THRESHOLD = 120;

function useScrollReveal() {
  const refs = useRef<Record<string, HTMLElement | null>>({
    proof: null, how: null, features: null, demo: null, leaderboard: null, final: null,
  });
  const [visible, setVisible] = useState<Record<string, boolean>>({
    proof: false, how: false, features: false, demo: false, leaderboard: false, final: false,
  });
  const raf = useRef<number>(0);

  const check = useCallback(() => {
    const vh = typeof window !== 'undefined' ? window.innerHeight : 800;
    const trigger = vh - REVEAL_THRESHOLD;
    setVisible((prev) => {
      let next: Record<string, boolean> | null = null;
      for (const key of Object.keys(refs.current)) {
        const el = refs.current[key as keyof typeof refs.current];
        if (!el) continue;
        const top = el.getBoundingClientRect().top;
        if (top <= trigger && !prev[key]) {
          if (!next) next = { ...prev };
          next[key] = true;
        }
      }
      return next || prev;
    });
  }, []);

  useEffect(() => {
    const run = () => {
      raf.current = 0;
      check();
    };
    const onScroll = () => {
      if (raf.current) return;
      raf.current = requestAnimationFrame(run);
    };
    check();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', run);
    const t = setTimeout(check, 200);
    const t2 = setTimeout(check, 600);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', run);
      clearTimeout(t);
      clearTimeout(t2);
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [check]);

  const setRef = useCallback((key: string) => (el: HTMLElement | null) => {
    refs.current[key] = el;
    if (el) requestAnimationFrame(check);
  }, [check]);

  return { visible, setRef };
}

const NAV_ITEMS = [
  { label: 'How It Works', href: '#how' },
  { label: 'Features', href: '#features' },
  { label: 'Leaderboard', href: '#leaderboard' },
];

const STEPS = [
  {
    step: '01',
    title: 'Prove your baseline',
    desc: 'You run a quick, pressure-tested assessment. Hidden tests score your speed and correctness in real time.',
    visual: 'ASSESSMENT',
  },
  {
    step: '02',
    title: 'Get a live match',
    desc: 'Our matcher pairs you with someone at your edge. Same language, similar skill, zero waiting room drama.',
    visual: 'MATCH ENGINE',
  },
  {
    step: '03',
    title: 'Clash and climb',
    desc: 'Both players solve the same problem. First correct submit wins the round and moves up the ladder.',
    visual: 'LIVE ARENA',
  },
];

const FEATURES = [
  { icon: '⚡', title: 'Live 1v1 Battles', desc: 'Race to first accepted solution.', code: 'DUEL', signal: 'Latency lock < 45ms' },
  { icon: '🧪', title: 'Hidden Test Judge', desc: 'No shortcut passes. Only robust code.', code: 'VERIFY', signal: 'Private test gates + anti-cheat' },
  { icon: '🎯', title: 'Skill Matchmaking', desc: 'Opponents close enough to challenge.', code: 'PAIR', signal: 'Adaptive ELO skill bands' },
  { icon: '📈', title: 'ELO Progression', desc: 'Every match shifts your rank story.', code: 'RANK', signal: 'Live rating deltas after each round' },
  { icon: '🐳', title: 'Sandbox Execution', desc: 'Isolated runs inside Docker containers.', code: 'SANDBOX', signal: 'Containerized runtime per submit' },
  { icon: '🏁', title: 'Seasonal Ladders', desc: 'Fresh climbs, badges, and bragging rights.', code: 'SEASON', signal: 'Resets, rewards, and title races' },
];

const TESTIMONIALS = [
  { name: 'Riya / @bit-arc', text: 'CodeClash feels like esports for developers. Every match spikes my heartbeat.', tag: 'Top 1%' },
  { name: 'Ishan / @rustvoid', text: 'I stopped grinding random question lists. This gives me focused pressure practice.', tag: '2,641 ELO' },
  { name: 'Mira / @pythonic', text: 'The hidden tests are ruthless in the best way. My production code quality improved fast.', tag: 'Staff Engineer' },
];

export default function Home() {
  const { user, loading } = useAuth();
  const [heroReady, setHeroReady] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [activeFeature, setActiveFeature] = useState(0);

  const { onlineNow, matchesToday, avgQueueMs } = useLiveStats();
  const activityFeed = useLiveFeed();

  useCursor();
  const { visible: reveal, setRef: setRevealRef } = useScrollReveal();

  useEffect(() => {
    const t = setTimeout(() => setHeroReady(true), 120);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!reveal.demo) return;
    const ticker = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % STEPS.length);
    }, 2100);
    return () => clearInterval(ticker);
  }, [reveal.demo]);

  useEffect(() => {
    if (!reveal.features) return;
    const ticker = setInterval(() => {
      setActiveFeature((prev) => (prev + 1) % FEATURES.length);
    }, 2300);
    return () => clearInterval(ticker);
  }, [reveal.features]);

  const statItems = useMemo(
    () => [
      `PLAYERS ONLINE ${onlineNow.toLocaleString()}`,
      `MATCHES TODAY ${matchesToday.toLocaleString()}`,
      `AVG QUEUE ${avgQueueMs}ms`,
      'WIN RATE SPREAD 49.8% / 50.2%',
      'RATING UPDATES < 120ms',
    ],
    [onlineNow, matchesToday, avgQueueMs]
  );

  if (loading) return <div className="landing-loading">SYNCING ARENA...</div>;

  return (
    <>
      <div className="ambient-grid" aria-hidden />
      <div className="cursor-dot" aria-hidden />
      <div className="cursor-ring" aria-hidden />

      <nav className="landing-nav">
        <Link href="/" className="brand">
          CODECLASH
        </Link>
        <div className="nav-links">
          {NAV_ITEMS.map((item) => (
            <a key={item.href} href={item.href} className="nav-link cursor-hover">
              {item.label}
            </a>
          ))}
        </div>
        <Link href={user ? '/dashboard' : '/register'} className="btn btn-primary cursor-hover">
          {user ? 'Open Dashboard' : 'Start Climbing'}
        </Link>
      </nav>

      <main className="landing-main">
        <section id="hero" className="hero">
          <div className="hero-copy">
            <p className={`hero-kicker reveal-stagger ${heroReady ? 'in' : ''}`} style={{ '--delay': '0s' } as CSSProperties}>
              LIVE CODING DUELS
            </p>
            <h1 className={`hero-title reveal-stagger ${heroReady ? 'in' : ''}`} style={{ '--delay': '0.1s' } as CSSProperties}>
              Outcode someone in real time.
            </h1>
            <p className={`hero-subtitle reveal-stagger ${heroReady ? 'in' : ''}`} style={{ '--delay': '0.2s' } as CSSProperties}>
              Competitive programming arena for developers and students who want pressure, speed, and real skill growth.
            </p>
            <div className={`hero-actions reveal-stagger ${heroReady ? 'in' : ''}`} style={{ '--delay': '0.3s' } as CSSProperties}>
              <Link href={user ? '/dashboard' : '/register'} className="btn btn-primary cursor-hover">
                {user ? 'Go To Dashboard' : 'Enter Arena'}
              </Link>
              <Link href="/login" className="btn btn-secondary cursor-hover">
                Watch Live Match
              </Link>
            </div>
            <div className={`hero-signal reveal-stagger ${heroReady ? 'in' : ''}`} style={{ '--delay': '0.4s' } as CSSProperties}>
              <span>QUEUE ~ {avgQueueMs}ms</span>
              <span>ONLINE {onlineNow.toLocaleString()}</span>
              <span>MATCHES {matchesToday.toLocaleString()}</span>
            </div>
          </div>

          <div className={`hero-visual reveal-stagger ${heroReady ? 'in' : ''}`} style={{ '--delay': '0.2s' } as CSSProperties}>
            <div className="arena-grid" />
            <div className="arena-beam beam-1" />
            <div className="arena-beam beam-2" />
            <div className="arena-node node-1" />
            <div className="arena-node node-2" />
            <div className="arena-node node-3" />
            <div className="core-ring ring-1" />
            <div className="core-ring ring-2" />
            <div className="core-ring ring-3" />
            <div className="scan-cone" />
            <div className="orbit orbit-a"><span /></div>
            <div className="orbit orbit-b"><span /></div>
            <div className="data-rain" aria-hidden>
              <span>1010110</span><span>0110011</span><span>1101010</span><span>0010111</span>
            </div>
            <div className="duel-line duel-a" />
            <div className="duel-line duel-b" />
            <div className="duel-card left">
              <span>PLAYER A</span>
              <strong>accepted.py</strong>
              <em>72% complete</em>
            </div>
            <div className="duel-card right">
              <span>PLAYER B</span>
              <strong>solver.cpp</strong>
              <em>69% complete</em>
            </div>
            <div className="duel-center">
              <b>00:43</b>
              <small>LIVE ROUND</small>
            </div>
          </div>
        </section>

        <section ref={setRevealRef('proof')} className={`proof-bar reveal ${reveal.proof ? 'in' : ''}`}>
          <div className="proof-track">
            {[...statItems, ...statItems].map((item, idx) => (
              <span key={`${item}-${idx}`}>{item}</span>
            ))}
          </div>
        </section>

        <section id="how" ref={setRevealRef('how')} className={`how reveal ${reveal.how ? 'in' : ''}`}>
          <header className="section-head">
            <p>HOW IT WORKS</p>
            <h2>Three beats. One obsession: better under pressure.</h2>
          </header>
          <div className="how-grid">
            {STEPS.map((step) => (
              <article key={step.step} className="step-card cursor-hover">
                <div className="step-visual">{step.visual}</div>
                <span>{step.step}</span>
                <h3>{step.title}</h3>
                <p>{step.desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="features" ref={setRevealRef('features')} className={`features reveal ${reveal.features ? 'in' : ''}`}>
          <header className="section-head">
            <p>FEATURES</p>
            <h2>Built for coders who hate easy mode.</h2>
          </header>
          <div className="feature-arena">
            <div className="feature-stage" aria-hidden>
              <div className="stage-ring stage-ring-a" />
              <div className="stage-ring stage-ring-b" />
              <div className="stage-ring stage-ring-c" />
              <div className="stage-sweep" />
              {FEATURES.map((feature, idx) => (
                <div
                  key={feature.title}
                  className={`feature-orbit-node ${activeFeature === idx ? 'active' : ''}`}
                  style={{ '--index': idx, '--count': FEATURES.length } as CSSProperties}
                >
                  <span>{feature.icon}</span>
                </div>
              ))}
              <div className="stage-core">
                <small>{FEATURES[activeFeature].code}</small>
                <strong>{FEATURES[activeFeature].title}</strong>
                <em>{FEATURES[activeFeature].signal}</em>
              </div>
            </div>

            <div className="feature-rail">
              {FEATURES.map((feature, idx) => (
                <button
                  key={feature.title}
                  type="button"
                  className={`feature-node cursor-hover ${activeFeature === idx ? 'active' : ''}`}
                  onMouseEnter={() => setActiveFeature(idx)}
                  onFocus={() => setActiveFeature(idx)}
                >
                  <span className="feature-icon">{feature.icon}</span>
                  <span className="feature-copy">
                    <b>{feature.title}</b>
                    <i>{feature.desc}</i>
                  </span>
                  <span className="feature-code">{feature.code}</span>
                </button>
              ))}
              <div className="feature-progress">
                <div className="feature-progress-fill" style={{ width: `${((activeFeature + 1) / FEATURES.length) * 100}%` }} />
              </div>
              <p className="feature-signal">{FEATURES[activeFeature].signal}</p>
            </div>
          </div>
          <div className="feature-grid" aria-hidden>
            {FEATURES.map((feature) => (
              <article key={feature.title} className="feature-card cursor-hover">
                <div className="feature-icon">{feature.icon}</div>
                <h3>{feature.title}</h3>
                <p>{feature.desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section ref={setRevealRef('demo')} className={`demo reveal ${reveal.demo ? 'in' : ''}`}>
          <header className="section-head">
            <p>LIVE PREVIEW</p>
            <h2>Feel the match flow before you sign up.</h2>
          </header>
          <div className="demo-arena">
            <div className="demo-timeline">
              {STEPS.map((step, idx) => (
                <button
                  key={step.step}
                  type="button"
                  className={`timeline-node cursor-hover ${activeStep === idx ? 'active' : ''}`}
                  onMouseEnter={() => setActiveStep(idx)}
                >
                  {step.step}
                </button>
              ))}
            </div>
            <div className="demo-panel wow-pulse">
              <h3>{STEPS[activeStep].title}</h3>
              <p>{STEPS[activeStep].desc}</p>
              <div className="demo-meter">
                <div className="demo-meter-fill" style={{ width: `${(activeStep + 1) * 32}%` }} />
              </div>
              <small>Round signal: stable • low latency • judge armed</small>
            </div>
          </div>
        </section>

        <section id="leaderboard" ref={setRevealRef('leaderboard')} className={`leaderboard reveal ${reveal.leaderboard ? 'in' : ''}`}>
          <header className="section-head">
            <p>ARENA FEED</p>
            <h2>People are climbing right now.</h2>
          </header>
          <div className="leader-layout">
            <div className="live-feed">
              {activityFeed.map((line: { id: string; time: string; text: string }) => (
                <div key={line.id} className="feed-line">
                  <span>{line.time}</span>
                  <p>{line.text}</p>
                </div>
              ))}
            </div>
            <div className="testimonials">
              {TESTIMONIALS.map((item) => (
                <article key={item.name} className="quote-card cursor-hover">
                  <p>“{item.text}”</p>
                  <div>
                    <strong>{item.name}</strong>
                    <span>{item.tag}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section ref={setRevealRef('final')} className={`final-cta reveal ${reveal.final ? 'in' : ''}`}>
          <p>DON&apos;T JUST PRACTICE. PERFORM.</p>
          <h2>{onlineNow.toLocaleString()} developers are in the arena right now.</h2>
          <Link href="/register" className="btn btn-primary cursor-hover">
            Claim Your Handle
          </Link>
        </section>
      </main>

      <footer className="landing-footer">
        <span>CODECLASH</span>
        <span>War room coding. Code or be coded.</span>
        <span>Next.js · FastAPI · PostgreSQL · Docker</span>
      </footer>
    </>
  );
}

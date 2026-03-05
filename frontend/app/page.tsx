'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState, type CSSProperties, type RefObject } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useCursor } from './js/cursor';
import { useReveal } from './js/reveal';
import { useLiveStats, useLiveFeed } from './js/live';

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
  { icon: '⚡', title: 'Live 1v1 Battles', desc: 'Race to first accepted solution.' },
  { icon: '🧪', title: 'Hidden Test Judge', desc: 'No shortcut passes. Only robust code.' },
  { icon: '🎯', title: 'Skill Matchmaking', desc: 'Opponents close enough to challenge.' },
  { icon: '📈', title: 'ELO Progression', desc: 'Every match shifts your rank story.' },
  { icon: '🐳', title: 'Sandbox Execution', desc: 'Isolated runs inside Docker containers.' },
  { icon: '🏁', title: 'Seasonal Ladders', desc: 'Fresh climbs, badges, and bragging rights.' },
];

const TESTIMONIALS = [
  { name: 'Riya / @bit-arc', text: 'CodeClash feels like esports for developers. Every match spikes my heartbeat.', tag: 'Top 1%' },
  { name: 'Ishan / @rustvoid', text: 'I stopped grinding random question lists. This gives me focused pressure practice.', tag: '2,641 ELO' },
  { name: 'Mira / @pythonic', text: 'The hidden tests are ruthless in the best way. My production code quality improved fast.', tag: 'Staff Engineer' },
];

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [heroReady, setHeroReady] = useState(false);
  const [activeStep, setActiveStep] = useState(0);

  const { onlineNow, matchesToday, avgQueueMs } = useLiveStats();
  const activityFeed = useLiveFeed();

  useCursor();

  const [heroRef, heroVisible] = useReveal() as [RefObject<HTMLElement>, boolean];
  const [proofRef, proofVisible] = useReveal() as [RefObject<HTMLElement>, boolean];
  const [howRef, howVisible] = useReveal() as [RefObject<HTMLElement>, boolean];
  const [featuresRef, featuresVisible] = useReveal() as [RefObject<HTMLElement>, boolean];
  const [demoRef, demoVisible] = useReveal() as [RefObject<HTMLElement>, boolean];
  const [leaderRef, leaderVisible] = useReveal() as [RefObject<HTMLElement>, boolean];
  const [finalRef, finalVisible] = useReveal() as [RefObject<HTMLElement>, boolean];

  useEffect(() => {
    if (!loading && user) router.push('/dashboard');
  }, [loading, user, router]);

  useEffect(() => {
    const t = setTimeout(() => setHeroReady(true), 120);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!demoVisible) return;
    const ticker = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % STEPS.length);
    }, 2100);
    return () => clearInterval(ticker);
  }, [demoVisible]);

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
        <Link href="/register" className="btn btn-primary cursor-hover">
          Start Climbing
        </Link>
      </nav>

      <main className="landing-main">
        <section id="hero" ref={heroRef} className={`hero reveal ${heroVisible ? 'in' : ''}`}>
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
            <Link href="/register" className="btn btn-primary cursor-hover">
              Enter Arena
            </Link>
            <Link href="/login" className="btn btn-secondary cursor-hover">
              Watch Live Match
            </Link>
          </div>

          <div className={`hero-visual reveal-stagger ${heroReady ? 'in' : ''}`} style={{ '--delay': '0.4s' } as CSSProperties}>
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

        <section ref={proofRef} className={`proof-bar reveal ${proofVisible ? 'in' : ''}`}>
          <div className="proof-track">
            {[...statItems, ...statItems].map((item, idx) => (
              <span key={`${item}-${idx}`}>{item}</span>
            ))}
          </div>
        </section>

        <section id="how" ref={howRef} className={`how reveal ${howVisible ? 'in' : ''}`}>
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

        <section id="features" ref={featuresRef} className={`features reveal ${featuresVisible ? 'in' : ''}`}>
          <header className="section-head">
            <p>FEATURES</p>
            <h2>Built for coders who hate easy mode.</h2>
          </header>
          <div className="feature-grid">
            {FEATURES.map((feature) => (
              <article key={feature.title} className="feature-card cursor-hover">
                <div className="feature-icon">{feature.icon}</div>
                <h3>{feature.title}</h3>
                <p>{feature.desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section ref={demoRef} className={`demo reveal ${demoVisible ? 'in' : ''}`}>
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

        <section id="leaderboard" ref={leaderRef} className={`leaderboard reveal ${leaderVisible ? 'in' : ''}`}>
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

        <section ref={finalRef} className={`final-cta reveal ${finalVisible ? 'in' : ''}`}>
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

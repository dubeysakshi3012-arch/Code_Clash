'use client';

import { useEffect } from 'react';

export function useCursor() {
  useEffect(() => {
    const dot = document.querySelector('.cursor-dot');
    const ring = document.querySelector('.cursor-ring');
    if (!dot || !ring) return;

    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const coarsePointer = window.matchMedia('(hover: none), (pointer: coarse)').matches;
    if (prefersReduced || coarsePointer) {
      dot.remove();
      ring.remove();
      return;
    }

    document.body.classList.add('custom-cursor');

    const state = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const lag = { x: state.x, y: state.y };
    let rafId = 0;

    const onMove = (e) => {
      state.x = e.clientX;
      state.y = e.clientY;
      dot.style.transform = `translate3d(${state.x}px, ${state.y}px, 0)`;
    };

    const onPointerOver = (e) => {
      const interactive = e.target.closest('.cursor-hover, a, button');
      if (interactive) {
        document.body.classList.add('cursor-active');
      } else {
        document.body.classList.remove('cursor-active');
      }
    };

    const tick = () => {
      lag.x += (state.x - lag.x) * 0.14;
      lag.y += (state.y - lag.y) * 0.14;
      ring.style.transform = `translate3d(${lag.x}px, ${lag.y}px, 0)`;
      rafId = requestAnimationFrame(tick);
    };

    dot.style.opacity = '1';
    ring.style.opacity = '1';
    rafId = requestAnimationFrame(tick);

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerover', onPointerOver);

    return () => {
      cancelAnimationFrame(rafId);
      document.body.classList.remove('custom-cursor', 'cursor-active');
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerover', onPointerOver);
    };
  }, []);
}

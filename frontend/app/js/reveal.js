'use client';

import { useCallback, useLayoutEffect, useRef, useState } from 'react';

/**
 * Robust scroll reveal: IntersectionObserver + throttled scroll fallback.
 * Triggers when element enters viewport (80px lead for smooth UX).
 */
export function useReveal() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  const fired = useRef(false);

  const reveal = useCallback(() => {
    if (fired.current) return;
    fired.current = true;
    setVisible(true);
  }, []);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    const check = () => {
      const rect = el.getBoundingClientRect();
      const vh = window.innerHeight;
      if (rect.top < vh - 80 && rect.bottom > -50) reveal();
    };

    check();
    if (fired.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) reveal();
      },
      { root: null, rootMargin: '100px 0px 100px 0px', threshold: 0 }
    );
    observer.observe(el);

    let raf = 0;
    const onScroll = () => {
      if (raf || fired.current) return;
      raf = requestAnimationFrame(() => {
        check();
        raf = 0;
      });
    };

    window.addEventListener('scroll', onScroll, { passive: true });

    const t = setTimeout(check, 150);

    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', onScroll);
      clearTimeout(t);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [reveal]);

  return [ref, visible];
}

'use client';

import { useEffect, useRef, useState } from 'react';

export function useReveal() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  const fired = useRef(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || fired.current) return;

    const reveal = () => {
      if (fired.current) return;
      fired.current = true;
      setVisible(true);
    };

    const inViewport = () => {
      const box = node.getBoundingClientRect();
      return box.top < window.innerHeight - 48 && box.bottom > 0;
    };

    if (inViewport()) {
      reveal();
      return;
    }

    const cleanup = [];

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            reveal();
            observer.disconnect();
          }
        },
        { threshold: 0, rootMargin: '0px 0px -48px 0px' }
      );
      observer.observe(node);
      cleanup.push(() => observer.disconnect());
    }

    const onScroll = () => {
      if (inViewport()) reveal();
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    cleanup.push(() => window.removeEventListener('scroll', onScroll));

    return () => cleanup.forEach((fn) => fn());
  }, []);

  return [ref, visible];
}

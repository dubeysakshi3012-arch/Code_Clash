'use client';

import { useEffect, useMemo, useState } from 'react';

const BASE_FEED = [
  'ananya solved Array Relay in 41s',
  'devon jumped to 2,312 ELO',
  'karim won a 7-round streak',
  'sara cleared hidden edge-case suite',
  'mike hit #19 on ladder',
];

export function useLiveStats() {
  const [onlineNow, setOnlineNow] = useState(1834);
  const [matchesToday, setMatchesToday] = useState(12944);
  const [avgQueueMs, setAvgQueueMs] = useState(96);

  useEffect(() => {
    const t = setInterval(() => {
      setOnlineNow((v) => v + (Math.random() > 0.5 ? 1 : -1) * Math.floor(Math.random() * 4));
      setMatchesToday((v) => v + Math.floor(Math.random() * 3));
      setAvgQueueMs(88 + Math.floor(Math.random() * 21));
    }, 1800);

    return () => clearInterval(t);
  }, []);

  return { onlineNow: Math.max(1680, onlineNow), matchesToday, avgQueueMs };
}

export function useLiveFeed() {
  const initial = useMemo(
    () =>
      BASE_FEED.map((text, i) => ({
        id: `${Date.now()}-${i}`,
        time: `${12 + i}:${String(11 + i).padStart(2, '0')}`,
        text,
      })),
    []
  );

  const [feed, setFeed] = useState(initial);

  useEffect(() => {
    const t = setInterval(() => {
      const next = BASE_FEED[Math.floor(Math.random() * BASE_FEED.length)];
      const stamp = new Date();
      const time = `${String(stamp.getHours()).padStart(2, '0')}:${String(stamp.getMinutes()).padStart(2, '0')}`;
      setFeed((prev) => [{ id: `${stamp.getTime()}`, time, text: next }, ...prev].slice(0, 6));
    }, 2300);

    return () => clearInterval(t);
  }, []);

  return feed;
}

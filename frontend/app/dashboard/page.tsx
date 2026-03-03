'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { authApi } from '@/lib/api';
import { createSocketConnection, type MatchFoundPayload } from '@/lib/socket';

export default function DashboardPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const router = useRouter();
  const [searching, setSearching] = useState(false);
  const [matchError, setMatchError] = useState<string | null>(null);
  const socketRef = useRef<ReturnType<typeof createSocketConnection> | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  const disconnectSocket = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }
  }, []);

  const handleFindMatch = async () => {
    if (!user) return;
    setMatchError(null);
    setSearching(true);
    // Ensure token is valid (trigger refresh if expired) before opening socket
    const meResponse = await authApi.getMe();
    if (meResponse.error) {
      setMatchError(meResponse.error === 'Session expired' ? 'Session expired. Please log in again.' : meResponse.error);
      setSearching(false);
      return;
    }
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    if (!token) {
      setMatchError('Please log in again.');
      setSearching(false);
      return;
    }
    const socket = createSocketConnection(token);
    socketRef.current = socket;

    socket.on('connect_error', (err) => {
      setMatchError(err.message || 'Could not connect to matchmaking.');
      setSearching(false);
      disconnectSocket();
    });

    socket.on('match_found', (payload: MatchFoundPayload) => {
      setSearching(false);
      disconnectSocket();
      if (payload.match_id) {
        router.push(`/match/${payload.match_id}`);
      } else {
        setMatchError(
          'The match could not be created. The question generator may be temporarily unavailable. Please try again.'
        );
      }
    });

    socket.on('match_create_error', (payload: { message?: string }) => {
      setSearching(false);
      disconnectSocket();
      setMatchError(payload?.message || 'Could not create match. Please try again.');
    });

    socket.on('matchmaking_timeout', () => {
      setMatchError('Search timed out. Try again.');
      setSearching(false);
      disconnectSocket();
    });

    socket.on('matchmaking_cancelled', () => {
      setSearching(false);
      disconnectSocket();
    });

    socket.connect();
    socket.emit('find_match', { language: user.selected_language || undefined });
  };

  const handleCancelFindMatch = () => {
    if (socketRef.current) {
      socketRef.current.emit('cancel_find_match');
      setSearching(false);
      disconnectSocket();
    }
  };

  useEffect(() => {
    return () => disconnectSocket();
  }, [disconnectSocket]);

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="text-lg text-zinc-600 dark:text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const hasElo = user.elo_rating > 0;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <nav className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <span className="text-xl font-bold text-black dark:text-zinc-50">CodeClash</span>
            <div className="flex items-center gap-4">
              <Link
                href="/assessment"
                className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
              >
                Assessment
              </Link>
              <span className="text-sm text-zinc-600 dark:text-zinc-400">{user.email}</span>
              <button
                onClick={logout}
                className="rounded-md px-3 py-1 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <section className="rounded-lg bg-white p-6 shadow-lg dark:bg-zinc-900">
            <h1 className="text-2xl font-bold text-black dark:text-zinc-50">Dashboard</h1>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Your hub for stats and matchmaking.
            </p>
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="text-lg font-semibold text-black dark:text-zinc-50">Your Stats</h2>
            <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-3xl font-bold text-black dark:text-zinc-50">
                  ELO: {user.elo_rating}
                </div>
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                  {hasElo
                    ? 'Keep practicing to improve your rating.'
                    : 'Complete an assessment to get your initial ELO rating.'}
                </p>
              </div>
              {user.selected_language && (
                <div className="text-sm text-zinc-600 dark:text-zinc-400">
                  Language: <span className="capitalize font-medium text-zinc-800 dark:text-zinc-200">{user.selected_language}</span>
                </div>
              )}
            </div>
          </section>

          {!hasElo && (
            <section className="rounded-lg border border-amber-200 bg-amber-50 p-6 dark:border-amber-800 dark:bg-amber-900/20">
              <h2 className="text-lg font-semibold text-amber-900 dark:text-amber-100">Get your ELO rating</h2>
              <p className="mt-1 text-sm text-amber-800 dark:text-amber-200">
                Start the placement assessment to get matched with players at your level.
              </p>
              <Link
                href="/assessment"
                className="mt-4 inline-block rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 dark:bg-amber-500 dark:hover:bg-amber-600"
              >
                Start placement assessment
              </Link>
            </section>
          )}

          <section className="rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="text-lg font-semibold text-black dark:text-zinc-50">Find a match</h2>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Queue for a coding match with another player.
            </p>
            {matchError && (
              <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-900/20">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-200">{matchError}</p>
                <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                  You can try again in a moment or check back later.
                </p>
              </div>
            )}
            {searching ? (
              <div className="mt-4 flex gap-2">
                <span className="flex flex-1 items-center justify-center rounded-md border border-zinc-200 bg-zinc-50 py-3 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400">
                  Searching for match…
                </span>
                <button
                  onClick={handleCancelFindMatch}
                  className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-700"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={handleFindMatch}
                disabled={!hasElo}
                className="mt-4 w-full rounded-md bg-green-600 px-4 py-3 font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50 dark:bg-green-500 dark:hover:bg-green-600"
              >
                Find Match
              </button>
            )}
            {!hasElo && (
              <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                Complete the placement assessment to get your ELO and find matches.
              </p>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

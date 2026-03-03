'use client';

import React from 'react';

interface ViolationWarningModalProps {
  isOpen: boolean;
  violationCount: number;
  message: string;
  onClose: () => void;
}

/**
 * Warning modal for assessment violations
 * Displays progressive warnings (1st, 2nd, final)
 * Styled with subtle amber/yellow theme, non-aggressive
 */
export default function ViolationWarningModal({
  isOpen,
  violationCount,
  message,
  onClose,
}: ViolationWarningModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-zinc-900">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/30">
            <span className="text-xl">⚠️</span>
          </div>
          <h2 className="text-xl font-semibold text-black dark:text-zinc-50">
            Assessment Warning
          </h2>
        </div>
        <p className="mb-6 text-zinc-700 dark:text-zinc-300">{message}</p>
        <div className="mb-4 rounded-md bg-amber-50 p-3 dark:bg-amber-900/20">
          <p className="text-sm text-amber-800 dark:text-amber-200">
            Violations: {violationCount} / 3
          </p>
        </div>
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="rounded-md bg-amber-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-600 dark:bg-amber-600 dark:hover:bg-amber-700"
          >
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
}

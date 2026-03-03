'use client';

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';

const ASSESSMENT_DURATION_SECONDS = 2400; // 40 minutes

export type UrgencyLevel = 'normal' | 'warning' | 'critical';

export interface TimerState {
  timeLeft: number; // seconds remaining
  formattedTime: string; // "MM:SS"
  urgencyLevel: UrgencyLevel;
  isExpired: boolean;
}

/**
 * Custom hook for managing assessment timer with persistence
 * 
 * Features:
 * - 40 minute countdown timer
 * - Persists across page reloads using localStorage
 * - Accurate timing using Date.now()
 * - Color-coded urgency levels
 * - Auto-expires when time runs out
 */
export function useAssessmentTimer(assessmentId: number): TimerState {
  const [timeLeft, setTimeLeft] = useState<number>(ASSESSMENT_DURATION_SECONDS);
  const [isExpired, setIsExpired] = useState<boolean>(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const hasInitializedRef = useRef<boolean>(false);

  // Get localStorage key for this assessment
  const storageKey = useMemo(
    () => `assessment_${assessmentId}_start_time`,
    [assessmentId]
  );

  // Initialize timer from localStorage or create new one
  const initializeTimer = useCallback(() => {
    if (hasInitializedRef.current) return;
    hasInitializedRef.current = true;

    try {
      const storedStartTime = localStorage.getItem(storageKey);
      const now = Date.now();

      if (storedStartTime) {
        // Resume existing timer
        const startTime = parseInt(storedStartTime, 10);
        const elapsedSeconds = Math.floor((now - startTime) / 1000);
        const remaining = ASSESSMENT_DURATION_SECONDS - elapsedSeconds;

        if (remaining <= 0) {
          // Timer already expired
          setTimeLeft(0);
          setIsExpired(true);
          startTimeRef.current = startTime;
        } else {
          // Timer still running
          setTimeLeft(remaining);
          startTimeRef.current = startTime;
        }
      } else {
        // Create new timer
        localStorage.setItem(storageKey, now.toString());
        startTimeRef.current = now;
        setTimeLeft(ASSESSMENT_DURATION_SECONDS);
      }
    } catch (error) {
      // localStorage unavailable, use in-memory timer
      console.warn('localStorage unavailable, using in-memory timer:', error);
      const now = Date.now();
      startTimeRef.current = now;
      setTimeLeft(ASSESSMENT_DURATION_SECONDS);
    }
  }, [storageKey]);

  // Update timer every second
  useEffect(() => {
    initializeTimer();

    const updateTimer = () => {
      if (!startTimeRef.current) return;

      try {
        const storedStartTime = localStorage.getItem(storageKey);
        if (storedStartTime) {
          const startTime = parseInt(storedStartTime, 10);
          const now = Date.now();
          const elapsedSeconds = Math.floor((now - startTime) / 1000);
          const remaining = ASSESSMENT_DURATION_SECONDS - elapsedSeconds;

          if (remaining <= 0) {
            setTimeLeft(0);
            setIsExpired(true);
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
          } else {
            setTimeLeft(remaining);
          }
        }
      } catch (error) {
        // Fallback to in-memory calculation if localStorage fails
        if (startTimeRef.current) {
          const now = Date.now();
          const elapsedSeconds = Math.floor((now - startTimeRef.current) / 1000);
          const remaining = ASSESSMENT_DURATION_SECONDS - elapsedSeconds;

          if (remaining <= 0) {
            setTimeLeft(0);
            setIsExpired(true);
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
          } else {
            setTimeLeft(remaining);
          }
        }
      }
    };

    // Update immediately
    updateTimer();

    // Set up interval
    intervalRef.current = setInterval(updateTimer, 1000);

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [storageKey, initializeTimer]);

  // Format time as MM:SS
  const formattedTime = useMemo(() => {
    const minutes = Math.floor(timeLeft / 60);
    const seconds = timeLeft % 60;
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }, [timeLeft]);

  // Determine urgency level based on remaining time
  const urgencyLevel = useMemo<UrgencyLevel>(() => {
    if (isExpired || timeLeft <= 0) {
      return 'critical';
    }
    if (timeLeft < 300) {
      // Less than 5 minutes
      return 'critical';
    }
    if (timeLeft < 900) {
      // Less than 15 minutes (5-15 minutes)
      return 'warning';
    }
    // More than 15 minutes
    return 'normal';
  }, [timeLeft, isExpired]);

  return {
    timeLeft,
    formattedTime,
    urgencyLevel,
    isExpired,
  };
}

/**
 * Cleanup function to remove timer from localStorage
 * Call this when assessment completes or user exits
 */
export function cleanupAssessmentTimer(assessmentId: number): void {
  try {
    const storageKey = `assessment_${assessmentId}_start_time`;
    localStorage.removeItem(storageKey);
  } catch (error) {
    console.warn('Failed to cleanup timer from localStorage:', error);
  }
}

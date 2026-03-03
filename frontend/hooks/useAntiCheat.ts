'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { assessmentApi } from '@/lib/api';

export type ViolationType = 'fullscreen_exit' | 'tab_switch' | 'window_blur';

export interface AntiCheatState {
  violationCount: number;
  isLocked: boolean;
  showWarning: boolean;
  warningMessage: string;
  /** When true, user left fullscreen – assessment is paused until they re-enter via requestFullscreen */
  showFullscreenRequired: boolean;
  /** Call to re-enter fullscreen and continue assessment */
  requestFullscreen: () => Promise<void>;
  triggerAutoSubmit: () => void;
}

const MAX_VIOLATIONS = 3; // Auto-submit after 3 violations
const DEBOUNCE_MS = 500; // Debounce rapid events

/**
 * Custom hook for anti-cheating monitoring during assessments
 * 
 * Features:
 * - Forces fullscreen mode on mount
 * - Tracks violations: fullscreen exit, tab switch, window blur
 * - Maintains violation count (max 3 before auto-submit)
 * - Debounces rapid events to prevent false positives
 * - Auto-submits assessment on threshold violation
 * - Cleans up listeners on unmount
 */
export function useAntiCheat(
  assessmentId: number,
  onAutoSubmit: () => void
): AntiCheatState {
  const [violationCount, setViolationCount] = useState<number>(0);
  const [isLocked, setIsLocked] = useState<boolean>(false);
  const [showWarning, setShowWarning] = useState<boolean>(false);
  const [warningMessage, setWarningMessage] = useState<string>('');
  const [showFullscreenRequired, setShowFullscreenRequired] = useState<boolean>(false);

  const autoSubmitTriggeredRef = useRef<boolean>(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastViolationTimeRef = useRef<number>(0);
  const fullscreenAttemptedRef = useRef<boolean>(false);

  // Request fullscreen (reusable so we can re-enter after user exits)
  const requestFullscreen = useCallback(async () => {
    try {
      const element = document.documentElement;
      if (element.requestFullscreen) {
        await element.requestFullscreen();
      } else if ((element as any).webkitRequestFullscreen) {
        await (element as any).webkitRequestFullscreen();
      } else if ((element as any).mozRequestFullScreen) {
        await (element as any).mozRequestFullScreen();
      } else if ((element as any).msRequestFullscreen) {
        await (element as any).msRequestFullscreen();
      }
    } catch (error) {
      console.warn('Failed to request fullscreen:', error);
    }
  }, []);

  // Request fullscreen on mount
  useEffect(() => {
    if (fullscreenAttemptedRef.current) return;
    fullscreenAttemptedRef.current = true;
    requestFullscreen();
  }, [requestFullscreen]);

  // Log violation to backend
  const logViolation = useCallback(async (violationType: ViolationType) => {
    try {
      const apiResponse = await assessmentApi.logViolation(assessmentId, violationType);
      
      if (apiResponse.error) {
        console.error('Failed to log violation:', apiResponse.error);
        // Non-blocking - continue monitoring even if logging fails
        return;
      }
      
      if (!apiResponse.data) {
        console.error('No data in violation log response');
        return;
      }
      
      const violationCount = apiResponse.data.violation_count;
      setViolationCount(violationCount);
      
      // Check if auto-submitted
      if (violationCount >= MAX_VIOLATIONS) {
        setIsLocked(true);
        setShowWarning(false);
        if (!autoSubmitTriggeredRef.current) {
          autoSubmitTriggeredRef.current = true;
          onAutoSubmit();
        }
      } else {
        // Show warning based on violation count
        if (violationCount === 1) {
          setWarningMessage('Warning: Leaving fullscreen or switching tabs may end your assessment.');
          setShowWarning(true);
        } else if (violationCount === 2) {
          setWarningMessage('Final Warning: One more violation will auto-submit your assessment.');
          setShowWarning(true);
        }
      }
    } catch (error) {
      console.error('Failed to log violation:', error);
      // Non-blocking - continue monitoring even if logging fails
    }
  }, [assessmentId, onAutoSubmit]);

  // Handle violation with debouncing
  const handleViolation = useCallback((violationType: ViolationType) => {
    if (isLocked || autoSubmitTriggeredRef.current) return;

    const now = Date.now();
    
    // Debounce rapid events
    if (now - lastViolationTimeRef.current < DEBOUNCE_MS) {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        handleViolation(violationType);
      }, DEBOUNCE_MS);
      return;
    }

    lastViolationTimeRef.current = now;
    logViolation(violationType);
  }, [isLocked, logViolation]);

  // Fullscreen change handler: on exit, stop assessment and show overlay; on re-enter, clear overlay
  useEffect(() => {
    const handleFullscreenChange = () => {
      const isFullscreen = !!(
        document.fullscreenElement ||
        (document as any).webkitFullscreenElement ||
        (document as any).mozFullScreenElement ||
        (document as any).msFullscreenElement
      );

      if (isFullscreen) {
        setShowFullscreenRequired(false);
        return;
      }

      if (isLocked || autoSubmitTriggeredRef.current) return;
      if (!fullscreenAttemptedRef.current) return;

      // User left fullscreen: log violation and show overlay – assessment paused until they re-enter
      handleViolation('fullscreen_exit');
      setShowFullscreenRequired(true);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, [isLocked, handleViolation]);

  // Tab switch / visibility change handler
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (isLocked || autoSubmitTriggeredRef.current) return;
      
      if (document.hidden) {
        handleViolation('tab_switch');
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isLocked, handleViolation]);

  // Window blur handler (additional detection)
  useEffect(() => {
    const handleBlur = () => {
      if (isLocked || autoSubmitTriggeredRef.current) return;
      
      // Only log if document is not hidden (to avoid double-counting with visibilitychange)
      if (!document.hidden) {
        handleViolation('window_blur');
      }
    };

    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('blur', handleBlur);
    };
  }, [isLocked, handleViolation]);

  // Cleanup debounce timer
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // Manual trigger for auto-submit
  const triggerAutoSubmit = useCallback(() => {
    if (!autoSubmitTriggeredRef.current && !isLocked) {
      autoSubmitTriggeredRef.current = true;
      setIsLocked(true);
      setShowWarning(false);
      onAutoSubmit();
    }
  }, [isLocked, onAutoSubmit]);

  return {
    violationCount,
    isLocked,
    showWarning,
    warningMessage,
    showFullscreenRequired,
    requestFullscreen,
    triggerAutoSubmit,
  };
}

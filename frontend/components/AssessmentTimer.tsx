'use client';

import { useAssessmentTimer, UrgencyLevel } from '@/hooks/useAssessmentTimer';

interface AssessmentTimerProps {
  assessmentId: number;
}

/**
 * AssessmentTimer Component
 * 
 * Displays a countdown timer in the top-right corner of the assessment page.
 * Shows color-coded urgency levels:
 * - White: >15 minutes remaining
 * - Yellow: 5-15 minutes remaining
 * - Red: <5 minutes remaining
 */
export default function AssessmentTimer({ assessmentId }: AssessmentTimerProps) {
  const { formattedTime, urgencyLevel, isExpired } = useAssessmentTimer(assessmentId);

  // Determine color classes based on urgency level
  const getColorClasses = (level: UrgencyLevel): string => {
    switch (level) {
      case 'normal':
        return 'text-white dark:text-zinc-50';
      case 'warning':
        return 'text-yellow-400 dark:text-yellow-500';
      case 'critical':
        return 'text-red-500 dark:text-red-400';
      default:
        return 'text-white dark:text-zinc-50';
    }
  };

  return (
    <div
      className={`fixed top-12 right-6 z-50 rounded-lg bg-black/80 px-4 py-2 shadow-lg backdrop-blur-sm dark:bg-white/10 ${getColorClasses(
        urgencyLevel
      )} transition-colors duration-300`}
    >
      <div className="flex items-center gap-2">
        <span className="text-lg">⏱</span>
        <span className={`text-lg font-semibold ${isExpired ? 'animate-pulse' : ''}`}>
          {isExpired ? '00:00' : formattedTime}
        </span>
      </div>
    </div>
  );
}

'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { assessmentApi } from '@/lib/api';
import ConfirmationModal from '@/components/ConfirmationModal';

export default function AssessmentEntryPage() {
  const { user, loading: authLoading, refreshUser } = useAuth();
  const router = useRouter();
  const [startingAssessment, setStartingAssessment] = useState(false);
  const [skippingAssessment, setSkippingAssessment] = useState(false);
  const [showSkipModal, setShowSkipModal] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<'python' | 'java' | 'cpp' | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
      return;
    }
    if (user && user.elo_rating > 0) {
      router.push('/dashboard');
    }
  }, [user, authLoading, router]);

  const handleStartAssessment = async () => {
    if (!selectedLanguage) {
      alert('Please select a programming language');
      return;
    }
    setStartingAssessment(true);
    try {
      const response = await assessmentApi.start(selectedLanguage);
      if (response.data) {
        router.push(`/assessment/${response.data.id}`);
      } else {
        alert(response.error || 'Failed to start assessment');
      }
    } catch (error) {
      console.error('Error starting assessment:', error);
      alert('Failed to start assessment. Please try again.');
    } finally {
      setStartingAssessment(false);
    }
  };

  const handleSkipAssessment = async () => {
    setSkippingAssessment(true);
    try {
      const response = await assessmentApi.skip(selectedLanguage || undefined);
      if (response.data) {
        await refreshUser();
        setShowSkipModal(false);
        router.push('/dashboard');
      } else {
        alert(response.error || 'Failed to skip assessment');
      }
    } catch (error) {
      console.error('Error skipping assessment:', error);
      alert('Failed to skip assessment. Please try again.');
    } finally {
      setSkippingAssessment(false);
    }
  };

  const shouldShowSkipButton = user && user.elo_rating === 0;

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

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <nav className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <Link href="/dashboard" className="text-xl font-bold text-black dark:text-zinc-50">
              CodeClash
            </Link>
            <Link
              href="/dashboard"
              className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
            >
              Dashboard
            </Link>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-lg px-4 py-12 sm:px-6 lg:px-8">
        <div className="rounded-lg bg-white p-8 shadow-lg dark:bg-zinc-900">
          <h1 className="text-2xl font-bold text-black dark:text-zinc-50">Placement Assessment</h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Select a language and start your assessment to get your ELO rating, or skip to begin as a beginner.
          </p>

          <div className="mt-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Programming Language
              </label>
              <div className="mt-2 flex gap-4">
                {(['python', 'java', 'cpp'] as const).map((lang) => (
                  <label key={lang} className="flex cursor-pointer items-center">
                    <input
                      type="radio"
                      name="language"
                      value={lang}
                      checked={selectedLanguage === lang}
                      onChange={() => setSelectedLanguage(lang)}
                      className="mr-2"
                    />
                    <span className="text-sm capitalize text-zinc-700 dark:text-zinc-300">{lang}</span>
                  </label>
                ))}
              </div>
            </div>

            <button
              onClick={handleStartAssessment}
              disabled={startingAssessment || skippingAssessment || !selectedLanguage}
              className="w-full rounded-md bg-black px-4 py-3 text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
            >
              {startingAssessment ? 'Starting...' : 'Start Assessment'}
            </button>

            {shouldShowSkipButton && (
              <button
                onClick={() => setShowSkipModal(true)}
                disabled={startingAssessment || skippingAssessment}
                className="w-full rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
              >
                Skip Assessment (Beginner Mode)
              </button>
            )}
          </div>
        </div>
      </main>

      <ConfirmationModal
        isOpen={showSkipModal}
        title="Skip Assessment?"
        message="Are you sure you want to skip the assessment? You'll be assigned a beginner ELO rating of 800. You can take the assessment later to improve your initial placement."
        confirmText="Yes, Skip"
        cancelText="Cancel"
        onConfirm={handleSkipAssessment}
        onCancel={() => setShowSkipModal(false)}
        confirmButtonStyle="bg-zinc-600 hover:bg-zinc-700"
      />
    </div>
  );
}

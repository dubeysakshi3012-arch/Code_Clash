'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { matchesApi, type MatchDetail, type MatchQuestionFull, type TestResultResponse, type TestCaseResult } from '@/lib/api';
import CodeEditor from '@/components/CodeEditor';

const POLL_INTERVAL_MS = 4000;

export default function MatchRoomPage() {
  const { user, loading: authLoading, refreshUser } = useAuth();
  const router = useRouter();
  const params = useParams();
  const matchId = params?.id ? Number(params.id) : NaN;
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [questions, setQuestions] = useState<MatchQuestionFull[]>([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [questionsError, setQuestionsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [lastSubmitResult, setLastSubmitResult] = useState<{
    is_correct: boolean;
    score: number;
    match_completed: boolean;
    winner_id: number | null;
  } | null>(null);
  const [matchCompletedFromSubmit, setMatchCompletedFromSubmit] = useState(false);
  const [iHaveFinishedAll, setIHaveFinishedAll] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState<TestResultResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [useCustomInput, setUseCustomInput] = useState(false);
  const [customInput, setCustomInput] = useState('');

  const refetchMatch = useCallback(() => {
    if (!matchId || isNaN(matchId)) return;
    matchesApi.getMatch(matchId).then((r) => {
      if (r.data) setMatch(r.data);
    });
  }, [matchId]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user || !matchId || isNaN(matchId)) return;
    matchesApi.getMatch(matchId).then((res) => {
      if (res.data) setMatch(res.data);
      else setError(res.error || 'Failed to load match');
    });
  }, [user, matchId]);

  useEffect(() => {
    if (!match || !user || match.status === 'completed' || match.status === 'abandoned') return;
    setQuestionsLoading(true);
    setQuestionsError(null);
    matchesApi
      .getMatchQuestions(matchId)
      .then((res) => {
        if (res.data && res.data.length > 0) {
          setQuestions(res.data);
          setAnswers(
            Object.fromEntries(
              res.data.map((q) => {
                const type = (q.type || 'coding').toLowerCase();
                const initial = type === 'coding' ? (q.starter_code ?? '') : '';
                return [q.id, initial];
              })
            )
          );
        } else if (res.error) {
          setQuestionsError(res.error);
        } else {
          setQuestionsError('No questions found for this match.');
        }
      })
      .catch(() => setQuestionsError('Failed to load questions.'))
      .finally(() => setQuestionsLoading(false));
  }, [match?.id, match?.status, matchId, user]);

  const opponent = match ? match.participants.find((p) => p.user_id !== user?.id) : null;
  const myParticipant = match ? match.participants.find((p) => p.user_id === user?.id) : null;
  const totalQuestions = questions.length;
  const mySubmissions = myParticipant?.submissions_count ?? 0;
  const opponentSubmissions = opponent?.submissions_count ?? 0;

  const isCompleted =
    match?.status === 'completed' ||
    match?.status === 'abandoned' ||
    matchCompletedFromSubmit;

  useEffect(() => {
    if (isCompleted && matchId && refreshUser) {
      refreshUser();
    }
  }, [isCompleted, matchId, refreshUser]);

  const totalSeconds = useMemo(() => {
    if (!match?.server_started_at || !match.time_limit_per_question || totalQuestions === 0)
      return null;
    const start = new Date(match.server_started_at).getTime();
    const total = match.time_limit_per_question * totalQuestions;
    return { start, total };
  }, [match?.server_started_at, match?.time_limit_per_question, totalQuestions]);

  const [timeLeftSeconds, setTimeLeftSeconds] = useState<number | null>(null);
  useEffect(() => {
    if (!totalSeconds || isCompleted) return;
    const tick = () => {
      const elapsed = (Date.now() - totalSeconds.start) / 1000;
      const left = Math.max(0, Math.floor(totalSeconds.total - elapsed));
      setTimeLeftSeconds(left);
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [totalSeconds, isCompleted]);

  const timerDisplay =
    timeLeftSeconds != null
      ? `${Math.floor(timeLeftSeconds / 60)}:${String(timeLeftSeconds % 60).padStart(2, '0')}`
      : '—';

  useEffect(() => {
    if (isCompleted || !matchId) return;
    const interval = setInterval(refetchMatch, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [isCompleted, matchId, refetchMatch]);

  useEffect(() => {
    setTestResults(null);
    setTestError(null);
    setCustomInput('');
    setUseCustomInput(false);
  }, [currentQuestionIndex]);

  function normalizeTestResult(data: TestResultResponse | undefined): TestResultResponse | null {
    if (!data) return null;
    const err = data.error?.trim();
    if (err && (err.startsWith('{') && (err.includes('"results"') || err.includes('"results":')))) {
      try {
        const parsed = JSON.parse(err) as { results?: TestCaseResult[]; execution_time?: number };
        if (Array.isArray(parsed.results) && parsed.results.length > 0) {
          const results = parsed.results;
          const passed = results.filter((r) => r?.passed).length;
          return { ...data, results, passed, total: results.length, execution_time: typeof parsed.execution_time === 'number' ? parsed.execution_time : data.execution_time, error: undefined };
        }
      } catch {
        /* keep original */
      }
    }
    return data;
  }

  const handleTestCode = async () => {
    const currentQuestion = questions[currentQuestionIndex];
    if (!currentQuestion || (currentQuestion.type || 'coding').toLowerCase() !== 'coding' || !match) return;
    const code = answers[currentQuestion.id] ?? currentQuestion.starter_code ?? '';
    if (!code.trim()) {
      alert('Please write some code first');
      return;
    }
    if (useCustomInput && !customInput.trim()) {
      alert('Please provide custom input');
      return;
    }
    setTesting(true);
    setTestResults(null);
    setTestError(null);
    try {
      const res = await matchesApi.testCode(
        matchId,
        currentQuestion.id,
        code,
        useCustomInput ? customInput : undefined
      );
      if (res.data) {
        setTestResults(normalizeTestResult(res.data) ?? res.data);
        setTestError(null);
      } else {
        const err = res.error ?? 'Failed to test code';
        if (err.includes('No visible test cases')) {
          setTestError('No visible test cases for this question. Use custom input or submit when ready.');
        } else if (err.includes('temporarily unavailable') || err.includes('503')) {
          setTestError('Code execution is temporarily unavailable. Please try again.');
        } else {
          setTestError(err || 'Failed to test code. Please try again.');
        }
      }
    } catch {
      setTestError('Failed to test code. Please try again.');
    } finally {
      setTesting(false);
    }
  };

  const handleSubmitAnswer = async () => {
    const currentQuestion = questions[currentQuestionIndex];
    if (!currentQuestion || !match || !user) return;
    const answer = answers[currentQuestion.id] ?? '';
    const qType = (currentQuestion.type || 'coding').toLowerCase() as 'mcq' | 'logic_trace' | 'coding';
    if (qType !== 'coding' && !answer.trim()) {
      alert('Please provide an answer');
      return;
    }

    setSubmitting(true);
    setLastSubmitResult(null);
    try {
      const body: {
        question_id: number;
        answer_type: 'mcq' | 'logic_trace' | 'coding';
        answer_data?: string | null;
        mcq_answer?: string | null;
      } = {
        question_id: currentQuestion.id,
        answer_type: qType,
      };
      if (qType === 'mcq') body.mcq_answer = answer.trim() || null;
      else body.answer_data = answer.trim() || null;

      const res = await matchesApi.submitAnswer(matchId, body);
      if (res.data) {
        setLastSubmitResult({
          is_correct: res.data.is_correct,
          score: res.data.score,
          match_completed: res.data.match_completed,
          winner_id: res.data.winner_id,
        });
        refetchMatch();
        if (res.data.match_completed) {
          setMatchCompletedFromSubmit(true);
          refreshUser();
        } else {
          const wasLastQuestion = currentQuestionIndex >= questions.length - 1;
          if (wasLastQuestion) {
            setIHaveFinishedAll(true);
          } else {
            setTimeout(() => {
              setCurrentQuestionIndex((i) => i + 1);
              setLastSubmitResult(null);
            }, 1500);
          }
        }
      } else {
        alert(res.error || 'Failed to submit answer');
      }
    } catch (e) {
      alert('Failed to submit answer. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="text-lg text-zinc-600 dark:text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (error || (!match && !questionsLoading)) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-black p-8">
        <p className="text-amber-600 dark:text-amber-400">{error || 'Match not found.'}</p>
        <Link href="/dashboard" className="mt-4 inline-block text-sm text-zinc-600 hover:underline dark:text-zinc-400">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  if (!match) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="text-center text-lg text-zinc-600 dark:text-zinc-400">
          Loading your match…
        </div>
      </div>
    );
  }

  if (!isCompleted && questionsLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="text-center">
          <div className="text-lg text-zinc-600 dark:text-zinc-400">
            Opponent found! Loading your personalized questions…
          </div>
          {opponent && (
            <p className="mt-2 text-sm text-zinc-500">You&apos;re matched with User #{opponent.user_id}</p>
          )}
        </div>
      </div>
    );
  }

  if (!isCompleted && questionsError) {
    const isAiUnavailable =
      questionsError.includes('AI') ||
      questionsError.includes('unavailable') ||
      questionsError.includes('could not generate');
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-black p-8">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 dark:border-amber-800 dark:bg-amber-900/20">
          <p className="font-medium text-amber-800 dark:text-amber-200">
            {isAiUnavailable ? questionsError : 'Questions could not be loaded.'}
          </p>
          {!isAiUnavailable && <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">{questionsError}</p>}
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">Please go back to the dashboard and try finding a new match.</p>
        </div>
        <Link href="/dashboard" className="mt-4 inline-block rounded-md bg-zinc-200 px-4 py-2 text-sm font-medium text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  if (isCompleted) {
    const winnerId = matchCompletedFromSubmit ? lastSubmitResult?.winner_id : match.winner_id;
    const myScore = myParticipant?.score ?? 0;
    const oppScore = opponent?.score ?? 0;
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-black">
        <nav className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-16 items-center justify-between">
              <span className="text-xl font-bold text-black dark:text-zinc-50">CodeClash</span>
              <Link href="/dashboard" className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
                Dashboard
              </Link>
            </div>
          </div>
        </nav>
        <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="rounded-xl border border-zinc-200 bg-white p-8 shadow-lg dark:border-zinc-800 dark:bg-zinc-900">
            <h1 className="text-2xl font-bold text-black dark:text-zinc-50">Match complete</h1>
            <p className="mt-2 text-zinc-600 dark:text-zinc-400">Well played! Your ELO has been updated.</p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
                <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">You</p>
                <p className="text-2xl font-bold text-black dark:text-zinc-50">{myScore} pts</p>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
                <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Opponent</p>
                <p className="text-2xl font-bold text-black dark:text-zinc-50">{oppScore} pts</p>
              </div>
            </div>
            <p className="mt-4 text-lg font-semibold text-zinc-800 dark:text-zinc-200">
              {winnerId == null ? 'Draw' : winnerId === user?.id ? 'You won!' : 'Opponent won'}
            </p>
            <Link href="/dashboard" className="mt-8 inline-block rounded-lg bg-black px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200">
              Back to Dashboard
            </Link>
          </div>
        </main>
      </div>
    );
  }

  if (iHaveFinishedAll && !isCompleted) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-black">
        <nav className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-16 items-center justify-between">
              <span className="text-xl font-bold text-black dark:text-zinc-50">CodeClash</span>
              <Link href="/dashboard" className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
                Dashboard
              </Link>
            </div>
          </div>
        </nav>
        <main className="mx-auto max-w-xl px-4 py-16 sm:px-6 lg:px-8">
          <div className="rounded-xl border border-zinc-200 bg-white p-8 shadow-lg dark:border-zinc-800 dark:bg-zinc-900">
            <div className="mb-4 flex justify-center">
              <div className="h-10 w-10 animate-spin rounded-full border-2 border-zinc-300 border-t-black dark:border-zinc-600 dark:border-t-white" />
            </div>
            <h1 className="text-center text-xl font-bold text-black dark:text-zinc-50">You&apos;ve finished!</h1>
            <p className="mt-2 text-center text-zinc-600 dark:text-zinc-400">
              Waiting for the opponent to complete the match. We&apos;ll update the result here when they&apos;re done.
            </p>
            <p className="mt-1 text-center text-sm text-zinc-500 dark:text-zinc-500">
              Opponent progress: {opponentSubmissions}/{totalQuestions} questions
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
              <button
                type="button"
                onClick={refetchMatch}
                className="rounded-lg border border-zinc-300 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
              >
                Check again
              </button>
              <Link
                href="/dashboard"
                className="rounded-lg bg-emerald-600 px-4 py-2.5 text-center text-sm font-medium text-white hover:bg-emerald-700 dark:bg-emerald-500 dark:hover:bg-emerald-600"
              >
                Find another match
              </Link>
              <Link
                href="/dashboard"
                className="rounded-lg border border-zinc-300 bg-zinc-100 px-4 py-2.5 text-center text-sm font-medium text-zinc-700 hover:bg-zinc-200 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
              >
                Back to dashboard
              </Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-black p-8">
        <p className="text-amber-600 dark:text-amber-400">No questions available.</p>
        <Link href="/dashboard" className="mt-4 inline-block text-sm text-zinc-600 hover:underline dark:text-zinc-400">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const currentQuestion = questions[currentQuestionIndex];
  if (!currentQuestion) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="text-lg text-zinc-600 dark:text-zinc-400">No question available</div>
      </div>
    );
  }

  const questionType = (currentQuestion.type || 'coding').toLowerCase() as 'mcq' | 'logic_trace' | 'coding';
  const matchLanguage = (match.language?.toLowerCase() || 'python') as 'python' | 'java' | 'cpp';

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <nav className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center justify-between">
            <span className="text-lg font-bold text-black dark:text-zinc-50">CodeClash · Match #{match.id}</span>
            <Link href="/dashboard" className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
              Dashboard
            </Link>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-6 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-4">
              <div className="rounded-lg bg-emerald-50 px-4 py-2 dark:bg-emerald-900/20">
                <p className="text-xs font-medium text-emerald-700 dark:text-emerald-300">You</p>
                <p className="text-lg font-bold text-emerald-800 dark:text-emerald-200">
                  {mySubmissions}/{totalQuestions} <span className="text-sm font-normal text-emerald-600 dark:text-emerald-400">questions</span>
                </p>
                {myParticipant?.score != null && (
                  <p className="text-xs text-emerald-600 dark:text-emerald-400">Score: {myParticipant.score}</p>
                )}
              </div>
              <div className="rounded-lg bg-zinc-100 px-4 py-2 dark:bg-zinc-800">
                <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Opponent (User #{opponent?.user_id ?? '?'})</p>
                <p className="text-lg font-bold text-zinc-800 dark:text-zinc-200">
                  {opponentSubmissions}/{totalQuestions} <span className="text-sm font-normal text-zinc-500 dark:text-zinc-400">questions</span>
                </p>
                {opponent?.score != null && <p className="text-xs text-zinc-500 dark:text-zinc-400">Score: {opponent.score}</p>}
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="rounded-md bg-zinc-100 px-3 py-1.5 text-sm font-medium text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200">
                {match.language}
              </span>
              <span className="rounded-md bg-amber-100 px-3 py-1.5 text-sm font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
                Time left: {timerDisplay}
              </span>
            </div>
          </div>
        </div>

        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
            Question {currentQuestionIndex + 1} of {totalQuestions}
          </p>
          <div className="h-2 flex-1 max-w-xs rounded-full bg-zinc-200 dark:bg-zinc-700 ml-4">
            <div
              className="h-full rounded-full bg-emerald-500 dark:bg-emerald-600 transition-all"
              style={{ width: `${((currentQuestionIndex + 1) / totalQuestions) * 100}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="text-xl font-semibold text-black dark:text-zinc-50">{currentQuestion.concept_name}</h2>
            <div className="mt-4 whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
              {currentQuestion.problem_statement || currentQuestion.logic_description || 'No description available'}
            </div>
            {questionType === 'mcq' && currentQuestion.options && (
              <div className="mt-6">
                <h3 className="font-semibold text-black dark:text-zinc-50">Options</h3>
                <div className="mt-2 space-y-2">
                  {Object.entries(currentQuestion.options).map(([key, value]) => (
                    <div key={key} className="rounded border border-zinc-200 p-3 dark:border-zinc-800">
                      <span className="font-medium text-zinc-800 dark:text-zinc-200">{key}:</span>{' '}
                      <span className="text-zinc-600 dark:text-zinc-400">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {questionType === 'coding' && currentQuestion.visible_test_cases && currentQuestion.visible_test_cases.length > 0 && (
              <div className="mt-6">
                <h3 className="font-semibold text-black dark:text-zinc-50">Test cases</h3>
                <div className="mt-2 space-y-2">
                  {currentQuestion.visible_test_cases.map((tc, idx) => (
                    <div key={idx} className="rounded border border-zinc-200 p-3 dark:border-zinc-800">
                      <p className="text-sm"><strong>Input:</strong> {tc.input_data ?? 'N/A'}</p>
                      <p className="mt-1 text-sm"><strong>Expected:</strong> {tc.expected_output}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="text-lg font-semibold text-black dark:text-zinc-50">
              {questionType === 'mcq' ? 'Select answer' : questionType === 'logic_trace' ? 'Your answer' : 'Your solution'}
            </h2>
            {lastSubmitResult && (
              <div
                className={`mt-4 rounded-lg border p-4 ${
                  lastSubmitResult.is_correct ? 'border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/20' : 'border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-900/20'
                }`}
              >
                <p className={lastSubmitResult.is_correct ? 'font-medium text-green-800 dark:text-green-200' : 'font-medium text-amber-800 dark:text-amber-200'}>
                  {lastSubmitResult.is_correct ? 'Correct!' : 'Incorrect'}
                </p>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">Score: +{lastSubmitResult.score}</p>
              </div>
            )}
            {questionType === 'mcq' && currentQuestion.options && (
              <div className="mt-4 space-y-2">
                {Object.entries(currentQuestion.options).map(([key, value]) => (
                  <label key={key} className="flex cursor-pointer items-center rounded-lg border border-zinc-200 p-3 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800">
                    <input
                      type="radio"
                      name={`q-${currentQuestion.id}`}
                      value={key}
                      checked={answers[currentQuestion.id] === key}
                      onChange={(e) => setAnswers({ ...answers, [currentQuestion.id]: e.target.value })}
                      disabled={submitting}
                      className="mr-3"
                    />
                    <span className="text-sm text-zinc-700 dark:text-zinc-300"><strong>{key}:</strong> {value}</span>
                  </label>
                ))}
              </div>
            )}
            {questionType === 'logic_trace' && (
              <input
                type="text"
                value={answers[currentQuestion.id] || ''}
                onChange={(e) => setAnswers({ ...answers, [currentQuestion.id]: e.target.value })}
                disabled={submitting}
                className="mt-4 w-full rounded-lg border border-zinc-300 p-3 text-sm focus:border-black focus:outline-none focus:ring-2 focus:ring-black/20 dark:border-zinc-600 dark:bg-zinc-800 dark:text-white dark:focus:border-white"
                placeholder="Enter your answer..."
              />
            )}
            {questionType === 'coding' && (() => {
              const hasVisibleTestCases = !!(currentQuestion.visible_test_cases && currentQuestion.visible_test_cases.length > 0);
              const canRunTest = hasVisibleTestCases || useCustomInput;
              return (
              <>
                <div className="mt-4">
                  <CodeEditor
                    value={answers[currentQuestion.id] || currentQuestion.starter_code || ''}
                    onChange={(value) => setAnswers({ ...answers, [currentQuestion.id]: value || '' })}
                    language={matchLanguage}
                    height="380px"
                    readOnly={submitting}
                  />
                </div>
                {(currentQuestion.time_limit || currentQuestion.memory_limit) && (
                  <div className="mt-3 flex justify-between text-xs text-zinc-500 dark:text-zinc-400">
                    {currentQuestion.time_limit && <span>Time: {currentQuestion.time_limit}s</span>}
                    {currentQuestion.memory_limit && <span>Memory: {currentQuestion.memory_limit}MB</span>}
                  </div>
                )}
                <div className="mt-4">
                  <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                    <input
                      type="checkbox"
                      checked={useCustomInput}
                      onChange={(e) => {
                        setUseCustomInput(e.target.checked);
                        if (!e.target.checked) {
                          setCustomInput('');
                          setTestResults(null);
                          setTestError(null);
                        }
                      }}
                      disabled={submitting}
                      className="rounded border-zinc-300 dark:border-zinc-600"
                    />
                    <span>Test with custom input</span>
                  </label>
                  {useCustomInput && (
                    <textarea
                      value={customInput}
                      onChange={(e) => setCustomInput(e.target.value)}
                      disabled={submitting}
                      placeholder="Enter custom input (e.g. space-separated numbers, JSON)"
                      className="mt-2 w-full rounded-lg border border-zinc-300 p-2 text-sm focus:border-black focus:outline-none focus:ring-2 focus:ring-black/20 dark:border-zinc-600 dark:bg-zinc-800 dark:text-white dark:focus:border-white"
                      rows={2}
                    />
                  )}
                </div>
                {!hasVisibleTestCases && !useCustomInput && (
                  <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
                    No sample test cases to run. Use custom input or submit when ready.
                  </p>
                )}
                {testError && (
                  <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
                    {testError}
                  </div>
                )}
                {testResults && (() => {
                  const results = testResults.results ?? [];
                  const total = (results.length || testResults.total) ?? 0;
                  const passed = results.length ? results.filter((r) => r.passed).length : (testResults.passed ?? 0);
                  const allPassed = total > 0 && passed === total;
                  const displayError = testResults.error?.trim();
                  return (
                    <div className="mt-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
                      <h3 className="mb-3 text-sm font-semibold text-black dark:text-zinc-50">Test results</h3>
                      {allPassed && !displayError ? (
                        <div className="rounded-lg border border-green-300 bg-green-50 p-3 dark:border-green-700 dark:bg-green-900/20">
                          <p className="text-sm font-medium text-green-800 dark:text-green-200">
                            All test cases passed ({passed}/{total})
                          </p>
                          {testResults.execution_time > 0 && (
                            <p className="mt-1 text-xs text-green-700 dark:text-green-300">
                              Time: {testResults.execution_time.toFixed(2)}s
                            </p>
                          )}
                        </div>
                      ) : (
                        <>
                          {total > 0 && (
                            <p className="mb-2 text-sm text-zinc-600 dark:text-zinc-400">
                              {passed}/{total} passed
                              {testResults.execution_time > 0 && ` · ${testResults.execution_time.toFixed(2)}s`}
                            </p>
                          )}
                          {results.filter((r) => !r.passed).map((r, idx) => (
                            <div
                              key={idx}
                              className="mb-2 rounded border border-red-200 bg-red-50 p-2 text-xs dark:border-red-800 dark:bg-red-900/20"
                            >
                              <p><strong>Input:</strong> {r.input}</p>
                              <p><strong>Expected:</strong> {r.expected_output}</p>
                              <p><strong>Got:</strong> {r.actual_output}</p>
                              {r.error && <p className="text-red-600 dark:text-red-400">{r.error}</p>}
                            </div>
                          ))}
                          {displayError && (
                            <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
                              {displayError}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  );
                })()}
                <div className="mt-4 flex gap-3">
                  <button
                    type="button"
                    onClick={handleTestCode}
                    disabled={testing || submitting || !canRunTest}
                    className="flex-1 rounded-lg border border-zinc-300 bg-white py-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
                  >
                    {testing ? 'Testing…' : 'Run/Test'}
                  </button>
                  <button
                    onClick={handleSubmitAnswer}
                    disabled={submitting || testing}
                    className="flex-1 rounded-lg bg-black py-3 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
                  >
                    {submitting ? 'Submitting…' : 'Submit answer'}
                  </button>
                </div>
              </>
              );
            })()}
            {questionType !== 'coding' && (
              <button
                onClick={handleSubmitAnswer}
                disabled={submitting}
                className="mt-4 w-full rounded-lg bg-black py-3 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
              >
                {submitting ? 'Submitting…' : 'Submit answer'}
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

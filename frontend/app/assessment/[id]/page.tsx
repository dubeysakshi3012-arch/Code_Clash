'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { assessmentApi, TestResultResponse, TestCaseResult } from '@/lib/api';
import CodeEditor from '@/components/CodeEditor';
import AssessmentTimer from '@/components/AssessmentTimer';
import ViolationWarningModal from '@/components/ViolationWarningModal';
import { useAssessmentTimer, cleanupAssessmentTimer } from '@/hooks/useAssessmentTimer';
import { useAntiCheat } from '@/hooks/useAntiCheat';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Returns true if the string looks like a JSON payload with "results" (backend sometimes sends this in error field). */
function looksLikeResultsJson(str: string): boolean {
  const t = str.trim();
  return t.startsWith('{') && (t.includes('"results"') || t.includes('"results":'));
}

/** Normalize test response: if error contains JSON with results, extract results and clear error so we never show JSON as error. */
function normalizeTestResult(data: TestResultResponse | undefined): TestResultResponse | null {
  if (!data) return null;
  const errorStr = data.error?.trim();
  if (errorStr && looksLikeResultsJson(errorStr)) {
    try {
      const parsed = JSON.parse(errorStr) as { results?: unknown[]; execution_time?: number };
      if (Array.isArray(parsed.results) && parsed.results.length > 0) {
        const results = parsed.results as TestCaseResult[];
        const passed = results.filter((r) => r && (r as TestCaseResult).passed).length;
        return {
          ...data,
          results,
          passed,
          total: results.length,
          execution_time: typeof parsed.execution_time === 'number' ? parsed.execution_time : data.execution_time,
          error: undefined,
        };
      }
    } catch {
      // Not valid JSON, keep original
    }
  }
  return data;
}

// Debug: Log API URL
if (typeof window !== 'undefined') {
  console.log('API_BASE_URL:', API_BASE_URL);
  console.log('NEXT_PUBLIC_API_URL env:', process.env.NEXT_PUBLIC_API_URL);
}

interface Question {
  id: number;
  concept_name: string;
  logic_description?: string;
  problem_statement?: string;
  starter_code?: string | null;
  time_limit?: number;
  memory_limit?: number;
  type?: 'mcq' | 'logic_trace' | 'coding';
  options?: Record<string, string>;
  visible_test_cases?: Array<{
    input?: string;
    input_data?: string;
    expected_output: string;
  }>;
  points?: number;
}

interface AssessmentProgress {
  section: string | null;
  current_section: string | null;
  section_a_completed: boolean;
  section_b_completed: boolean;
  section_c_completed: boolean;
}

export default function AssessmentPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const assessmentId = parseInt(params.id as string);

  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState<TestResultResponse | null>(null);
  const [completed, setCompleted] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [currentSection, setCurrentSection] = useState<string>('A');
  const [assessmentLanguage, setAssessmentLanguage] = useState<'python' | 'java' | 'cpp'>('python');
  const [progress, setProgress] = useState<AssessmentProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState<string>('');
  const [useCustomInput, setUseCustomInput] = useState(false);
  
  // Timer hook for global assessment timer
  const { isExpired } = useAssessmentTimer(assessmentId);
  const autoSubmitTriggeredRef = useRef<boolean>(false);

  const getAuthHeaders = () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    return {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    };
  };

  const completeAssessment = useCallback(async () => {
    try {
      setSubmitting(true);
      const url = `${API_BASE_URL}/api/v1/assessment/${assessmentId}/complete`;
      
      let response;
      try {
        response = await fetch(url, {
          method: 'POST',
          headers: getAuthHeaders(),
        });
      } catch (fetchError) {
        console.error('Fetch error:', fetchError);
        alert(`Network error: ${fetchError instanceof Error ? fetchError.message : 'Failed to connect to server'}`);
        setSubmitting(false);
        return;
      }

      if (!response.ok) {
        let errorMessage = 'Failed to complete assessment';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        }
        alert(errorMessage);
        setSubmitting(false);
        return;
      }

      const data = await response.json();
      setResults(data);
      setCompleted(true);
      setSubmitting(false);
      cleanupAssessmentTimer(assessmentId);
      
      try {
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        } else if ((document as any).webkitFullscreenElement) {
          await (document as any).webkitExitFullscreen();
        } else if ((document as any).mozFullScreenElement) {
          await (document as any).mozCancelFullScreen();
        } else if ((document as any).msFullscreenElement) {
          await (document as any).msExitFullscreen();
        }
      } catch (error) {
        console.log('Could not exit fullscreen:', error);
      }
    } catch (error) {
      console.error('Error completing assessment:', error);
      alert(`Failed to complete assessment: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setSubmitting(false);
    }
  }, [assessmentId]);

  // Anti-cheat hook (must be after completeAssessment is defined)
  const { violationCount, isLocked, showWarning, warningMessage, showFullscreenRequired, requestFullscreen, triggerAutoSubmit } = useAntiCheat(
    assessmentId,
    completeAssessment
  );
  const [showWarningModal, setShowWarningModal] = useState(false);

  // Sync showWarning state with modal
  useEffect(() => {
    setShowWarningModal(showWarning);
  }, [showWarning]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user && assessmentId) {
      loadProgress();
      loadQuestions();
    }
  }, [user, assessmentId]);

  // Auto-submit when timer expires
  useEffect(() => {
    if (isExpired && !autoSubmitTriggeredRef.current && !completed && !submitting) {
      autoSubmitTriggeredRef.current = true;
      console.log('Timer expired, auto-submitting assessment...');
      setSubmitting(true);
      completeAssessment();
    }
  }, [isExpired, completed, submitting, completeAssessment]);

  // Cleanup timer when assessment completes or user exits
  useEffect(() => {
    return () => {
      if (completed) {
        cleanupAssessmentTimer(assessmentId);
      }
    };
  }, [completed, assessmentId]);

  // Auto-redirect to dashboard after completion (user can still click "Go to Dashboard" immediately)
  useEffect(() => {
    if (!completed || !results) return;
    const t = setTimeout(() => router.push('/dashboard'), 4000);
    return () => clearTimeout(t);
  }, [completed, results, router]);

  const loadProgress = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/assessment/${assessmentId}/progress`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setProgress(data);
        if (data.current_section) {
          setCurrentSection(data.current_section);
        }
      }
    } catch (error) {
      console.error('Error loading progress:', error);
    }
  };

  const loadQuestions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/assessment/${assessmentId}/questions`, {
        headers: getAuthHeaders(),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to load questions' }));
        setError(errorData.detail || 'Failed to load questions');
        return;
      }

      const data = await response.json();
      if (data.questions && Array.isArray(data.questions)) {
        setQuestions(data.questions);
        if (data.section) {
          setCurrentSection(data.section);
        }
        if (data.language) {
          setAssessmentLanguage(data.language.toLowerCase() as 'python' | 'java' | 'cpp');
        }
      } else {
        setError('No questions found');
      }
    } catch (error) {
      console.error('Error loading questions:', error);
      setError('Failed to load questions. Please try again.');
    } finally {
      setLoading(false);
    }
  };


  const handleSubmitAnswer = async () => {
    const currentQuestion = questions[currentQuestionIndex];
    if (!currentQuestion) return;

    const answer = answers[currentQuestion.id] || '';
    if (!answer.trim()) {
      alert('Please provide an answer');
      return;
    }

    setSubmitting(true);
    
    try {
      let endpoint = '';
      let body: any = {};
      
      const questionType = currentQuestion.type || 'coding';
      
      if (questionType === 'mcq') {
        endpoint = `/api/v1/assessment/${assessmentId}/section/A/submit`;
        body = { question_id: currentQuestion.id, answer: answer };
      } else if (questionType === 'logic_trace') {
        endpoint = `/api/v1/assessment/${assessmentId}/section/B/submit`;
        body = { question_id: currentQuestion.id, answer: answer };
      } else {
        endpoint = `/api/v1/assessment/${assessmentId}/section/C/submit`;
        body = { question_id: currentQuestion.id, code: answer };
      }

      const fullUrl = `${API_BASE_URL}${endpoint}`;
      console.log('Submitting answer to:', fullUrl);
      console.log('Request body:', body);
      console.log('Headers:', getAuthHeaders());
      
      let response;
      try {
        response = await fetch(fullUrl, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(body),
        });
        console.log('Response status:', response.status);
      } catch (fetchError) {
        console.error('Fetch error:', fetchError);
        console.error('Error details:', {
          message: fetchError instanceof Error ? fetchError.message : 'Unknown',
          name: fetchError instanceof Error ? fetchError.name : 'Unknown',
          stack: fetchError instanceof Error ? fetchError.stack : undefined,
        });
        alert(`Network error: ${fetchError instanceof Error ? fetchError.message : 'Failed to connect to server'}\n\nPlease check:\n1. Backend server is running on ${API_BASE_URL}\n2. CORS is configured correctly\n3. Network connectivity`);
        return;
      }

      if (!response.ok) {
        let errorMessage = 'Failed to submit answer';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        }
        alert(errorMessage);
        return;
      }

      const data = await response.json();

      // Move to next question or complete section
      if (currentQuestionIndex < questions.length - 1) {
        setCurrentQuestionIndex(currentQuestionIndex + 1);
        setTestResults(null); // Clear test results when moving to next question
      } else {
        // Complete current section
        await completeSection();
      }
    } catch (error) {
      console.error('Error submitting answer:', error);
      alert('Failed to submit answer. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTestCode = async () => {
    const currentQuestion = questions[currentQuestionIndex];
    if (!currentQuestion || currentQuestion.type !== 'coding') return;

    const code = answers[currentQuestion.id] || currentQuestion.starter_code || '';
    if (!code.trim()) {
      alert('Please write some code first');
      return;
    }

    // If using custom input, validate it
    if (useCustomInput && !customInput.trim()) {
      alert('Please provide custom input');
      return;
    }

    setTesting(true);
    setTestResults(null);

    try {
      const response = await assessmentApi.testCode(
        assessmentId,
        currentQuestion.id,
        code,
        useCustomInput ? customInput : undefined
      );
      if (response.data) {
        setTestResults(normalizeTestResult(response.data) ?? response.data);
      } else {
        alert(response.error || 'Failed to test code');
      }
    } catch (error) {
      console.error('Error testing code:', error);
      alert('Failed to test code. Please try again.');
    } finally {
      setTesting(false);
    }
  };

  const completeSection = async () => {
    try {
      const url = `${API_BASE_URL}/api/v1/assessment/${assessmentId}/section/${currentSection}/complete`;
      console.log('Completing section:', url);
      
      let response;
      try {
        response = await fetch(url, {
          method: 'POST',
          headers: getAuthHeaders(),
        });
      } catch (fetchError) {
        console.error('Fetch error:', fetchError);
        alert(`Network error: ${fetchError instanceof Error ? fetchError.message : 'Failed to connect to server'}`);
        return;
      }

      if (!response.ok) {
        let errorMessage = 'Failed to complete section';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        }
        alert(errorMessage);
        return;
      }

      const data = await response.json();
      
      // If assessment is complete, show results
      if (data.is_complete) {
        await completeAssessment();
      } else {
        // Load next section questions
        setCurrentQuestionIndex(0);
        setAnswers({});
        await loadProgress();
        await loadQuestions();
      }
    } catch (error) {
      console.error('Error completing section:', error);
      alert(`Failed to complete section: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };


  if (authLoading || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  if (error && questions.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="text-lg text-red-600 dark:text-red-400">{error}</div>
          <button
            onClick={() => router.push('/dashboard')}
            className="mt-4 rounded-md bg-black px-4 py-2 text-white transition-colors hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (questions.length === 0 && !loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="text-lg">No questions found</div>
          <button
            onClick={() => router.push('/dashboard')}
            className="mt-4 rounded-md bg-black px-4 py-2 text-white transition-colors hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (completed && results) {
    const wasAutoSubmitted = !!results.auto_submitted;
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-black">
        <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="rounded-lg bg-white p-8 shadow-lg dark:bg-zinc-900">
            <h1 className="text-3xl font-bold text-black dark:text-zinc-50">Assessment Complete!</h1>
            {wasAutoSubmitted && (
              <p className="mt-2 rounded-md bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
                Your assessment was submitted automatically due to monitoring violations. Your ELO rating is shown below.
              </p>
            )}
            <div className="mt-6 space-y-4">
              <div className="text-lg">
                <strong>Total Score:</strong> {results.total_score || 0}
              </div>
              <div className="text-lg">
                <strong>Section A Score:</strong> {results.section_a_score || 0}
              </div>
              <div className="text-lg">
                <strong>Section B Score:</strong> {results.section_b_score || 0}
              </div>
              <div className="text-lg">
                <strong>Section C Score:</strong> {results.section_c_score || 0}
              </div>
              <div className="mt-6 rounded-lg border-2 border-green-500 bg-green-50 p-6 dark:bg-green-900/20">
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                  <strong>Your New ELO Rating:</strong> {results.new_elo_rating || 0}
                </div>
                <p className="mt-2 text-sm text-green-700 dark:text-green-300">
                  This rating determines your initial placement in CodeClash matches.
                </p>
              </div>
            </div>
            <div className="mt-8">
              <button
                onClick={() => router.push('/dashboard')}
                className="rounded-md bg-black px-4 py-2 text-white transition-colors hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
              >
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const currentQuestion = questions[currentQuestionIndex];
  if (!currentQuestion) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg">No question available</div>
      </div>
    );
  }

  const questionType = currentQuestion.type || 'coding';
  const sectionName = currentSection === 'A' ? 'MCQ' : currentSection === 'B' ? 'Logic & Trace' : 'Coding';

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      {/* Global Assessment Timer - only show when not completed */}
      {!completed && <AssessmentTimer assessmentId={assessmentId} />}
      
      {/* Fullscreen required overlay: assessment paused until user re-enters fullscreen */}
      {!completed && showFullscreenRequired && (
        <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black/90 px-4">
          <div className="max-w-md rounded-lg bg-white p-8 text-center shadow-xl dark:bg-zinc-900">
            <div className="mb-4 text-5xl">🔒</div>
            <h2 className="mb-2 text-xl font-bold text-black dark:text-zinc-50">Assessment paused</h2>
            <p className="mb-6 text-zinc-600 dark:text-zinc-400">
              You left fullscreen. To continue your assessment, return to fullscreen using the button below.
            </p>
            <button
              type="button"
              onClick={() => requestFullscreen()}
              className="w-full rounded-md bg-green-600 px-4 py-3 font-medium text-white transition-colors hover:bg-green-700 dark:bg-green-500 dark:hover:bg-green-600"
            >
              Continue in full screen
            </button>
          </div>
        </div>
      )}
      
      {/* Anti-cheat Violation Warning Modal - only show when not completed */}
      {!completed && (
        <ViolationWarningModal
          isOpen={showWarningModal}
          violationCount={violationCount}
          message={warningMessage}
          onClose={() => setShowWarningModal(false)}
        />
      )}
      
      {/* Monitoring Banner - slim strip at very top so it never overlaps Section header */}
      {!completed && (
        <div className="fixed top-0 left-0 right-0 z-40 flex h-10 items-center justify-center bg-blue-100/95 px-4 text-center text-xs text-blue-800 backdrop-blur-sm dark:bg-blue-900/40 dark:text-blue-200">
          <span>🔒 This assessment is monitored to ensure fair placement</span>
        </div>
      )}
      
      <div className={`mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8 ${!completed ? 'pt-20' : ''}`}>
        {/* Timer Expired Warning */}
        {isExpired && (
          <div className="mb-4 rounded-lg border-2 border-red-500 bg-red-50 p-4 dark:bg-red-900/20">
            <p className="text-center font-semibold text-red-800 dark:text-red-200">
              ⏱ Time's up! Your assessment is being automatically submitted...
            </p>
          </div>
        )}
        
        {/* Anti-cheat Lock Warning */}
        {isLocked && (
          <div className="mb-4 rounded-lg border-2 border-red-500 bg-red-50 p-4 dark:bg-red-900/20">
            <p className="text-center font-semibold text-red-800 dark:text-red-200">
              🔒 Assessment locked due to violations. Your assessment is being automatically submitted...
            </p>
          </div>
        )}
        
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-black dark:text-zinc-50">
              Section {currentSection}: {sectionName}
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Question {currentQuestionIndex + 1} of {questions.length}
            </p>
          </div>
          <button
            onClick={() => {
              cleanupAssessmentTimer(assessmentId);
              router.push('/dashboard');
            }}
            disabled={isLocked}
            className={`text-sm ${isLocked ? 'cursor-not-allowed opacity-50' : 'text-zinc-600 hover:underline'} dark:text-zinc-400`}
          >
            Exit Assessment
          </button>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-lg bg-white p-6 shadow-lg dark:bg-zinc-900">
            <h2 className="text-xl font-semibold text-black dark:text-zinc-50">
              {currentQuestion.concept_name}
            </h2>
            <div className="mt-4 whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
              {currentQuestion.problem_statement || currentQuestion.logic_description || 'No description available'}
            </div>
            
            {/* MCQ Options */}
            {questionType === 'mcq' && currentQuestion.options && (
              <div className="mt-6">
                <h3 className="font-semibold text-black dark:text-zinc-50">Options:</h3>
                <div className="mt-2 space-y-2">
                  {Object.entries(currentQuestion.options).map(([key, value]) => (
                    <div key={key} className="rounded border border-zinc-200 p-3 dark:border-zinc-800">
                      <div className="text-sm">
                        <strong>{key}:</strong> {value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Test Cases for Coding */}
            {questionType === 'coding' && currentQuestion.visible_test_cases && currentQuestion.visible_test_cases.length > 0 && (
              <div className="mt-6">
                <h3 className="font-semibold text-black dark:text-zinc-50">Test Cases:</h3>
                <div className="mt-2 space-y-2">
                  {currentQuestion.visible_test_cases.map((tc, idx) => (
                    <div key={idx} className="rounded border border-zinc-200 p-3 dark:border-zinc-800">
                      <div className="text-sm">
                        <strong>Input:</strong> {tc.input || tc.input_data || 'N/A'}
                      </div>
                      <div className="mt-1 text-sm">
                        <strong>Expected Output:</strong> {tc.expected_output}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-lg bg-white p-6 shadow-lg dark:bg-zinc-900">
            <h2 className="text-xl font-semibold text-black dark:text-zinc-50">
              {questionType === 'mcq' ? 'Select Answer' : questionType === 'logic_trace' ? 'Your Answer' : 'Your Solution'}
            </h2>
            
            {/* MCQ Questions */}
            {questionType === 'mcq' && currentQuestion.options && (
              <div className="mt-4 space-y-2">
                {Object.entries(currentQuestion.options).map(([key, value]) => (
                  <label key={key} className={`flex items-center rounded border border-zinc-200 p-3 dark:border-zinc-800 ${isExpired || isLocked ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800'}`}>
                    <input
                      type="radio"
                      name={`question-${currentQuestion.id}`}
                      value={key}
                      checked={answers[currentQuestion.id] === key}
                      onChange={(e) =>
                        setAnswers({ ...answers, [currentQuestion.id]: e.target.value })
                      }
                      disabled={isExpired || submitting || isLocked}
                      className="mr-3"
                    />
                    <span className="text-sm text-zinc-700 dark:text-zinc-300">
                      <strong>{key}:</strong> {value}
                    </span>
                  </label>
                ))}
              </div>
            )}
            
            {/* Logic & Trace Questions */}
            {questionType === 'logic_trace' && (
              <input
                type="text"
                value={answers[currentQuestion.id] || ''}
                onChange={(e) =>
                  setAnswers({ ...answers, [currentQuestion.id]: e.target.value })
                }
                disabled={isExpired || submitting || isLocked}
                className={`mt-4 w-full rounded-md border border-zinc-300 p-3 text-sm focus:border-black focus:outline-none focus:ring-black dark:border-zinc-600 dark:bg-zinc-800 dark:text-white dark:focus:border-white ${isExpired || isLocked ? 'cursor-not-allowed opacity-50' : ''}`}
                placeholder="Enter your answer..."
              />
            )}
            
            {/* Coding Questions */}
            {questionType === 'coding' && (
              <>
                <div className="mt-4">
                  <CodeEditor
                    value={answers[currentQuestion.id] || currentQuestion.starter_code || ''}
                    onChange={(value) =>
                      setAnswers({ ...answers, [currentQuestion.id]: value || '' })
                    }
                    language={assessmentLanguage}
                    height="400px"
                    readOnly={isExpired || submitting || isLocked}
                  />
                </div>
                {currentQuestion.time_limit && currentQuestion.memory_limit && (
                  <div className="mt-4 flex justify-between text-sm text-zinc-600 dark:text-zinc-400">
                    <span>Time Limit: {currentQuestion.time_limit}s</span>
                    <span>Memory Limit: {currentQuestion.memory_limit}MB</span>
                  </div>
                )}
                
                {/* Custom Input Option */}
                <div className="mt-4">
                  <label className={`flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300 ${isExpired || isLocked ? 'opacity-50 cursor-not-allowed' : ''}`}>
                    <input
                      type="checkbox"
                      checked={useCustomInput}
                      onChange={(e) => {
                        setUseCustomInput(e.target.checked);
                        if (!e.target.checked) {
                          setCustomInput('');
                          setTestResults(null);
                        }
                      }}
                      disabled={isExpired || submitting || isLocked}
                      className="rounded border-zinc-300 dark:border-zinc-600"
                    />
                    <span>Test with custom input</span>
                  </label>
                  {useCustomInput && (
                    <textarea
                      value={customInput}
                      onChange={(e) => setCustomInput(e.target.value)}
                      disabled={isExpired || submitting || isLocked}
                      placeholder="Enter custom input (e.g., space-separated numbers, JSON, etc.)"
                      className={`mt-2 w-full rounded-md border border-zinc-300 p-2 text-sm focus:border-black focus:outline-none focus:ring-black dark:border-zinc-600 dark:bg-zinc-800 dark:text-white dark:focus:border-white ${isExpired || isLocked ? 'cursor-not-allowed opacity-50' : ''}`}
                      rows={3}
                    />
                  )}
                </div>
                
                {/* Test Results Display */}
                {testResults && (() => {
                  const results = testResults.results ?? [];
                  const total = results.length || (testResults.total ?? 0);
                  const passed = results.length
                    ? results.filter((r) => r.passed).length
                    : (testResults.passed ?? 0);
                  const hasRealError = testResults.error?.trim() && !looksLikeResultsJson(testResults.error);
                  const displayError = hasRealError
                    ? testResults.error!
                        .split('\n')
                        .filter((line) => !line.trim().startsWith('Picked up JAVA_TOOL_OPTIONS'))
                        .join('\n')
                        .trim()
                    : null;
                  const allPassed = total > 0 && passed === total;
                  const someFailed = total > 0 && passed < total;
                  const failedCases = results.filter((r) => !r.passed);

                  return (
                    <div className="mt-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
                      <h3 className="mb-3 text-lg font-semibold text-black dark:text-zinc-50">
                        Test Results
                      </h3>

                      {/* Success: all test cases passed */}
                      {allPassed && !displayError && (
                        <div className="rounded-lg border border-green-300 bg-green-50 p-4 dark:border-green-700 dark:bg-green-900/20">
                          <p className="font-medium text-green-800 dark:text-green-200">
                            All test cases passed ({passed}/{total})
                          </p>
                          <div className="mt-2 flex flex-wrap gap-3 text-sm text-green-700 dark:text-green-300">
                            {testResults.execution_time > 0 && (
                              <span>Execution time: {testResults.execution_time.toFixed(2)}s</span>
                            )}
                            {typeof testResults.memory_used === 'number' && (
                              <span>Memory: {testResults.memory_used} MB</span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Partial: some failed */}
                      {someFailed && !displayError && (
                        <>
                          <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-700 dark:bg-amber-900/20">
                            <p className="font-medium text-amber-800 dark:text-amber-200">
                              {passed}/{total} test cases passed
                            </p>
                            <div className="mt-1 flex flex-wrap gap-3 text-sm text-amber-700 dark:text-amber-300">
                              {testResults.execution_time > 0 && (
                                <span>Execution time: {testResults.execution_time.toFixed(2)}s</span>
                              )}
                              {typeof testResults.memory_used === 'number' && (
                                <span>Memory: {testResults.memory_used} MB</span>
                              )}
                            </div>
                          </div>
                          <p className="mb-2 text-sm font-medium text-black dark:text-zinc-50">
                            Failed cases:
                          </p>
                          <div className="space-y-2">
                            {failedCases.map((result, idx) => (
                              <div
                                key={idx}
                                className="rounded border border-red-300 bg-red-50 p-3 dark:border-red-700 dark:bg-red-900/20"
                              >
                                <div className="flex items-center gap-2">
                                  <span className="text-red-600 dark:text-red-400">✗</span>
                                  <span className="font-medium text-black dark:text-zinc-50">
                                    Test case
                                  </span>
                                </div>
                                <div className="mt-2 space-y-1 text-sm">
                                  <div>
                                    <strong>Input:</strong>{' '}
                                    <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">
                                      {result.input}
                                    </code>
                                  </div>
                                  <div>
                                    <strong>Expected:</strong>{' '}
                                    <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">
                                      {result.expected_output}
                                    </code>
                                  </div>
                                  <div>
                                    <strong>Got:</strong>{' '}
                                    <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">
                                      {result.actual_output ?? '(no output)'}
                                    </code>
                                  </div>
                                  {result.error && (
                                    <div className="text-red-600 dark:text-red-400">
                                      <strong>Error:</strong> {result.error}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </>
                      )}

                      {/* Compilation / runtime error only (never raw JSON) */}
                      {displayError && (
                        <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-700 dark:bg-red-900/20 dark:text-red-200">
                          <strong>Error:</strong> {displayError}
                        </div>
                      )}

                      {/* When we have results but no summary box yet (e.g. custom input): show list + timing */}
                      {results.length > 0 && !allPassed && !someFailed && !displayError && (
                        <>
                          <div className="mb-2 text-sm text-zinc-600 dark:text-zinc-400">
                            {passed}/{total} passed
                            {testResults.execution_time > 0 && (
                              <span className="ml-2">
                                · Execution time: {testResults.execution_time.toFixed(2)}s
                              </span>
                            )}
                          </div>
                          <div className="space-y-2">
                            {results.map((result, idx) => (
                              <div
                                key={idx}
                                className={`rounded border p-3 ${
                                  result.passed
                                    ? 'border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/20'
                                    : 'border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/20'
                                }`}
                              >
                                <div className="flex items-center gap-2">
                                  <span className={result.passed ? 'text-green-600' : 'text-red-600'}>
                                    {result.passed ? '✓' : '✗'}
                                  </span>
                                  <span className="font-medium text-black dark:text-zinc-50">
                                    Test case {idx + 1}
                                  </span>
                                </div>
                                <div className="mt-2 space-y-1 text-sm">
                                  <div>
                                    <strong>Input:</strong>{' '}
                                    <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">
                                      {result.input}
                                    </code>
                                  </div>
                                  <div>
                                    <strong>Expected:</strong>{' '}
                                    <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">
                                      {result.expected_output}
                                    </code>
                                  </div>
                                  <div>
                                    <strong>Got:</strong>{' '}
                                    <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">
                                      {result.actual_output ?? '(no output)'}
                                    </code>
                                  </div>
                                  {result.error && (
                                    <div className="text-red-600 dark:text-red-400">
                                      <strong>Error:</strong> {result.error}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </>
                      )}

                      {/* Execution time when no results list shown (e.g. error-only response) */}
                      {results.length === 0 && testResults.execution_time > 0 && (
                        <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                          Execution time: {testResults.execution_time.toFixed(2)}s
                        </div>
                      )}
                    </div>
                  );
                })()}
                
                {/* Run/Test and Submit Buttons */}
                <div className="mt-4 flex gap-2">
                  <button
                    onClick={handleTestCode}
                    disabled={testing || submitting || isExpired || isLocked}
                    className="flex-1 rounded-md bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
                  >
                    {testing ? 'Testing...' : isExpired || isLocked ? 'Locked' : 'Run/Test'}
                  </button>
                  <button
                    onClick={handleSubmitAnswer}
                    disabled={submitting || testing || isExpired || isLocked}
                    className="flex-1 rounded-md bg-black px-4 py-2 text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
                  >
                    {isExpired
                      ? 'Submitting...'
                      : submitting
                      ? 'Submitting...'
                      : currentQuestionIndex < questions.length - 1
                      ? 'Submit & Next'
                      : `Complete Section ${currentSection}`}
                  </button>
                </div>
              </>
            )}
            
            {/* Submit button for non-coding questions */}
            {questionType !== 'coding' && (
              <button
                onClick={handleSubmitAnswer}
                disabled={submitting || isExpired || isLocked}
                className="mt-4 w-full rounded-md bg-black px-4 py-2 text-white transition-colors hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
              >
                {isExpired
                  ? 'Submitting...'
                  : submitting
                  ? 'Submitting...'
                  : currentQuestionIndex < questions.length - 1
                  ? 'Submit & Next'
                  : `Complete Section ${currentSection}`}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

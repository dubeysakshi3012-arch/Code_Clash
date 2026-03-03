/**
 * API client for CodeClash backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ApiResponse<T> {
  data?: T;
  error?: string;
}

export interface TestCaseResult {
  passed: boolean;
  input: string;
  expected_output: string;
  actual_output: string;
  error?: string;
}

export interface TestResultResponse {
  passed: number;
  total: number;
  results: TestCaseResult[];
  execution_time: number;
  error?: string;
  memory_used?: number;
}

/** Callback when session is expired (refresh failed or invalid). Use to clear auth state and redirect. */
export type OnSessionExpiredCallback = () => void;

class ApiClient {
  private baseURL: string;
  private onSessionExpired: OnSessionExpiredCallback | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  setOnSessionExpired(callback: OnSessionExpiredCallback | null): void {
    this.onSessionExpired = callback;
  }

  private clearTokensAndNotify(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
    this.onSessionExpired?.();
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    isRetry = false
  ): Promise<ApiResponse<T>> {
    // Get token from localStorage
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

    // Build headers - ensure Authorization is always set if token exists
    const headers: HeadersInit = new Headers();

    // Set Content-Type for requests with body
    if (options.method !== 'GET' && options.method !== 'HEAD') {
      headers.set('Content-Type', 'application/json');
    }

    // Copy any existing headers
    if (options.headers) {
      if (options.headers instanceof Headers) {
        options.headers.forEach((value, key) => {
          headers.set(key, value);
        });
      } else if (Array.isArray(options.headers)) {
        options.headers.forEach(([key, value]) => {
          headers.set(key, value);
        });
      } else {
        Object.entries(options.headers).forEach(([key, value]) => {
          headers.set(key, value as string);
        });
      }
    }

    // Always set Authorization header if token exists
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        headers,
        credentials: 'include',
      });

      // Handle 401 Unauthorized - try refresh once (except for refresh endpoint itself)
      if (response.status === 401) {
        const isRefreshEndpoint = endpoint.includes('/auth/refresh');
        if (isRefreshEndpoint || isRetry) {
          this.clearTokensAndNotify();
          const errorData = await response.json().catch(() => ({ detail: 'Unauthorized' }));
          return { error: errorData.detail || 'Authentication required' };
        }

        const refreshToken =
          typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null;
        if (!refreshToken) {
          this.clearTokensAndNotify();
          const errorData = await response.json().catch(() => ({ detail: 'Unauthorized' }));
          return { error: errorData.detail || 'Authentication required' };
        }

        const refreshRes = await fetch(`${this.baseURL}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
          credentials: 'include',
        });

        if (!refreshRes.ok) {
          this.clearTokensAndNotify();
          const errorData = await refreshRes.json().catch(() => ({ detail: 'Refresh failed' }));
          return { error: errorData.detail || 'Session expired' };
        }

        const refreshData = await refreshRes.json().catch(() => ({}));
        const newToken = refreshData?.access_token;
        if (!newToken) {
          this.clearTokensAndNotify();
          return { error: 'Session expired' };
        }

        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', newToken);
        }

        const retryHeaders = new Headers(headers);
        retryHeaders.set('Authorization', `Bearer ${newToken}`);
        const retryResponse = await fetch(`${this.baseURL}${endpoint}`, {
          ...options,
          headers: retryHeaders,
          credentials: 'include',
        });

        if (retryResponse.status === 401) {
          this.clearTokensAndNotify();
          const errorData = await retryResponse.json().catch(() => ({ detail: 'Unauthorized' }));
          return { error: errorData.detail || 'Authentication required' };
        }

        if (!retryResponse.ok) {
          const errorData = await retryResponse.json().catch(() => ({ detail: 'An error occurred' }));
          return { error: errorData.detail || `HTTP ${retryResponse.status}` };
        }

        const data = await retryResponse.json();
        return { data };
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'An error occurred' }));
        return { error: errorData.detail || `HTTP ${response.status}` };
      }

      const data = await response.json();
      return { data };
    } catch (error) {
      return { error: error instanceof Error ? error.message : 'Network error' };
    }
  }

  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async put<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient(API_BASE_URL);

// Auth API
export const authApi = {
  register: (email: string, password: string) =>
    apiClient.post<{ access_token: string; refresh_token: string }>('/api/v1/auth/register', {
      email,
      password,
    }),

  login: (email: string, password: string) =>
    apiClient.post<{ access_token: string; refresh_token: string }>('/api/v1/auth/login', {
      email,
      password,
    }),

  refreshToken: (refreshToken: string) =>
    apiClient.post<{ access_token: string }>('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    }),

  getMe: () => apiClient.get<{ id: number; email: string; elo_rating: number; selected_language: string | null }>('/api/v1/auth/me'),
};

// Assessment API
export const assessmentApi = {
  start: (language: 'python' | 'java' | 'cpp') =>
    apiClient.post<{ id: number; language: string; status: string }>('/api/v1/assessment/start', {
      language,
    }),

  getQuestions: (assessmentId: number) =>
    apiClient.get<{ questions: any[]; total: number }>(`/api/v1/assessment/${assessmentId}/questions`),

  submitAnswer: (assessmentId: number, questionId: number, answerType: string, answerData?: string, mcqAnswer?: string) =>
    apiClient.post(`/api/v1/assessment/${assessmentId}/submit`, {
      question_id: questionId,
      answer_type: answerType,
      answer_data: answerData,
      mcq_answer: mcqAnswer,
    }),

  complete: (assessmentId: number) =>
    apiClient.post<{ assessment_id: number; total_questions: number; correct_answers: number; score: number; new_elo_rating: number }>(
      `/api/v1/assessment/${assessmentId}/complete`
    ),

  testCode: (assessmentId: number, questionId: number, code: string, customInput?: string) =>
    apiClient.post<TestResultResponse>(`/api/v1/assessment/${assessmentId}/test`, {
      question_id: questionId,
      code: code,
      custom_input: customInput,
    }),

  skip: (selectedLanguage?: 'python' | 'java' | 'cpp') =>
    apiClient.post<{ status: string; elo_rating: number; message?: string }>('/api/v1/assessment/skip', {
      selected_language: selectedLanguage,
    }),

  logViolation: (assessmentId: number, violationType: 'fullscreen_exit' | 'tab_switch' | 'window_blur') =>
    apiClient.post<{ violation_count: number; message?: string }>(`/api/v1/assessment/${assessmentId}/log-violation`, {
      violation_type: violationType,
      timestamp: new Date().toISOString(),
    }),

  validateTimer: (assessmentId: number, clientTimeRemaining: number) =>
    apiClient.post<{ is_valid: boolean; server_time_remaining: number; difference: number; message?: string }>(
      `/api/v1/assessment/${assessmentId}/validate-timer`,
      {
        client_time_remaining: clientTimeRemaining,
      }
    ),
};

// Matches API (PvP)
export interface MatchDetail {
  id: number;
  status: string;
  winner_id: number | null;
  language: string;
  time_limit_per_question: number;
  server_started_at: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  participants: { user_id: number; score: number | null; left_at: string | null; submissions_count?: number }[];
  questions: { question_id: number; order: number }[];
}

/** Full question payload for match (same shape as assessment questions). */
export interface MatchQuestionFull {
  id: number;
  concept_name: string;
  logic_description?: string;
  problem_statement?: string;
  starter_code?: string | null;
  time_limit?: number;
  memory_limit?: number;
  type: 'mcq' | 'logic_trace' | 'coding';
  options?: Record<string, string>;
  visible_test_cases?: { input_data?: string; expected_output: string; order?: number }[];
  language?: string;
  points?: number;
}

export interface MatchSubmitBody {
  question_id: number;
  answer_type: 'mcq' | 'logic_trace' | 'coding';
  answer_data?: string | null;
  mcq_answer?: string | null;
}

export interface MatchSubmitResponse {
  score: number;
  is_correct: boolean;
  match_completed: boolean;
  winner_id: number | null;
}

export const matchesApi = {
  list: (params?: { limit?: number; offset?: number; status?: string }) => {
    const search = params ? new URLSearchParams(params as Record<string, string>).toString() : '';
    return apiClient.get<MatchDetail[]>(`/api/v1/matches${search ? `?${search}` : ''}`);
  },
  getMatch: (matchId: number) =>
    apiClient.get<MatchDetail>(`/api/v1/matches/${matchId}`),
  getMatchQuestions: (matchId: number) =>
    apiClient.get<MatchQuestionFull[]>(`/api/v1/matches/${matchId}/questions`),
  submitAnswer: (matchId: number, body: MatchSubmitBody) =>
    apiClient.post<MatchSubmitResponse>(`/api/v1/matches/${matchId}/submit`, body),
  testCode: (matchId: number, questionId: number, code: string, customInput?: string) =>
    apiClient.post<TestResultResponse>(`/api/v1/matches/${matchId}/test`, {
      question_id: questionId,
      code,
      custom_input: customInput,
    }),
};

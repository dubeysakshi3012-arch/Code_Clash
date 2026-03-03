/**
 * Socket.io client for CodeClash matchmaking.
 * Connect with JWT; emit find_match / cancel_find_match; listen for match_found, matchmaking_timeout, matchmaking_cancelled.
 */

import { io, Socket } from 'socket.io-client';

const SOCKET_URL = process.env.NEXT_PUBLIC_SOCKET_URL || 'http://localhost:3001';

export type MatchFoundPayload = {
  match_id: number | null;
  opponent: { user_id: number };
  language: string;
  question_count: number;
  time_per_question: number;
  question_ids?: number[];
};

export function createSocketConnection(accessToken: string): Socket {
  return io(SOCKET_URL, {
    auth: { token: accessToken },
    transports: ['websocket', 'polling'],
  });
}

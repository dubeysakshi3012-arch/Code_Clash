require('dotenv').config();
const http = require('http');
const { Server } = require('socket.io');
const jwt = require('jsonwebtoken');

const PORT = process.env.PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET_KEY;
const API_URL = (process.env.API_URL || 'http://localhost:8000').replace(/\/$/, '');
const SOCKET_SECRET = process.env.SOCKET_SERVER_SECRET;
const CORS_ORIGINS = (process.env.CORS_ORIGINS || 'http://localhost:3000,http://localhost:5173').split(',').map(s => s.trim());

if (!JWT_SECRET) {
  console.error('JWT_SECRET_KEY is required');
  process.exit(1);
}

const app = http.createServer();
const io = new Server(app, {
  cors: {
    origin: CORS_ORIGINS,
    methods: ['GET', 'POST'],
    credentials: true,
  },
});

// Queue: userId -> { socketId, elo, language, joinedAt }
const queue = new Map();
const ELO_BAND = 150;
const QUEUE_TIMEOUT_MS = 120000; // 2 minutes
const timeoutHandles = new Map(); // userId -> setTimeout handle

function removeFromQueue(userId) {
  queue.delete(userId);
  const handle = timeoutHandles.get(userId);
  if (handle) {
    clearTimeout(handle);
    timeoutHandles.delete(userId);
  }
}

function findMatch(userId, elo, language) {
  const lang = language || null;
  for (const [otherId, other] of queue.entries()) {
    if (otherId === userId) continue;
    const eloOk = Math.abs((other.elo || 1000) - (elo || 1000)) <= ELO_BAND;
    const langOk = !lang || !other.language || other.language === lang;
    if (eloOk && langOk) {
      return otherId;
    }
  }
  return null;
}

io.use((socket, next) => {
  const token = socket.handshake.auth?.token || socket.handshake.query?.token;
  if (!token) {
    return next(new Error('Authentication required'));
  }
  try {
    const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] });
    if (payload.type !== 'access') {
      return next(new Error('Access token required'));
    }
    const userId = parseInt(payload.sub, 10);
    if (!userId) return next(new Error('Invalid token'));
    socket.data.userId = userId;
    socket.data.elo = payload.elo ?? 1000;
    socket.data.wins = payload.wins ?? 0;
    socket.data.losses = payload.losses ?? 0;
    next();
  } catch (err) {
    next(new Error('Invalid or expired token'));
  }
});

io.on('connection', (socket) => {
  const userId = socket.data.userId;
  const elo = socket.data.elo;

  socket.on('find_match', async (payload) => {
    const language = payload?.language || null;
    removeFromQueue(userId);
    queue.set(userId, {
      socketId: socket.id,
      elo,
      language,
      joinedAt: Date.now(),
    });
    const handle = setTimeout(() => {
      if (queue.get(userId)?.socketId === socket.id) {
        removeFromQueue(userId);
        socket.emit('matchmaking_timeout', { message: 'Queue timeout' });
      }
      timeoutHandles.delete(userId);
    }, QUEUE_TIMEOUT_MS);
    timeoutHandles.set(userId, handle);

    const otherId = findMatch(userId, elo, language);
    if (otherId != null) {
      const other = queue.get(otherId);
      if (!other) return;
      removeFromQueue(userId);
      removeFromQueue(otherId);
      const otherSocket = io.sockets.sockets.get(other.socketId);
      if (!otherSocket) return;
      const lang = language || other.language || 'python';
      const participantIds = [userId, otherId];
      if (SOCKET_SECRET && API_URL) {
        try {
          const res = await fetch(`${API_URL}/api/v1/matches/create`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Socket-Secret': SOCKET_SECRET,
            },
            body: JSON.stringify({
              participant_user_ids: participantIds,
              language: lang,
              question_ids: null,
              time_limit_per_question: 300,
            }),
          });
          if (res.ok) {
            const data = await res.json();
            const matchPayload = {
              match_id: data.match_id,
              opponent: { user_id: otherId },
              language: lang,
              question_count: (data.question_ids || []).length,
              time_per_question: data.time_limit_per_question || 300,
              question_ids: data.question_ids || [],
            };
            socket.join(`match:${data.match_id}`);
            otherSocket.join(`match:${data.match_id}`);
            socket.emit('match_found', matchPayload);
            otherSocket.emit('match_found', {
              ...matchPayload,
              opponent: { user_id: userId },
            });
            return;
          }
          const errBody = await res.json().catch(() => ({}));
          let message = 'Could not create match. Please try again.';
          if (typeof errBody.detail === 'string') message = errBody.detail;
          else if (Array.isArray(errBody.detail) && errBody.detail[0]?.msg) message = errBody.detail[0].msg;
          else if (errBody.detail) message = String(errBody.detail);
          console.warn('Match create failed', res.status, message);
          socket.emit('match_create_error', { message });
          otherSocket.emit('match_create_error', { message });
          return;
        } catch (e) {
          console.error('Create match failed', e);
          const message = e && e.message ? e.message : 'Could not create match. Please try again.';
          socket.emit('match_create_error', { message });
          otherSocket.emit('match_create_error', { message });
          return;
        }
      }
      const matchPayload = {
        match_id: null,
        opponent: { user_id: otherId },
        language: lang,
        question_count: 3,
        time_per_question: 300,
      };
      socket.emit('match_found', matchPayload);
      otherSocket.emit('match_found', {
        ...matchPayload,
        opponent: { user_id: userId },
      });
    }
  });

  socket.on('cancel_find_match', () => {
    removeFromQueue(userId);
    socket.emit('matchmaking_cancelled', {});
  });

  socket.on('disconnect', () => {
    removeFromQueue(userId);
  });
});

app.listen(PORT, () => {
  console.log(`Socket server listening on port ${PORT}`);
});

// ============================================================
// OpenCode → PostgreSQL Sync Service
// Sincroniza el historial de OpenCode (SQLite) con PostgreSQL
// Base de datos: davey (EasyPanel)
// ============================================================

import pg from 'pg';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import os from 'os';

const { Pool } = pg;
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ── Conexión PostgreSQL (EasyPanel) ─────────────────────────
const DATABASE_URL = process.env.DATABASE_URL ||
  'postgres://postgres:6715320@35.254.218.190:5433/davey?sslmode=disable';

const pool = new Pool({ connectionString: DATABASE_URL });

// ── Ruta a la BD SQLite de OpenCode ─────────────────────────
function getOpencodeDbPath() {
  const platform = process.platform;
  if (platform === 'win32') {
    return path.join(os.homedir(), 'AppData', 'Local', 'opencode', 'opencode.db');
  }
  return path.join(os.homedir(), '.local', 'share', 'opencode', 'opencode.db');
}

// ── Crear tablas en PostgreSQL si no existen ────────────────
async function initDatabase() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS opencode_sessions (
        id          TEXT PRIMARY KEY,
        title       TEXT,
        created_at  TIMESTAMPTZ,
        updated_at  TIMESTAMPTZ,
        model       TEXT,
        synced_at   TIMESTAMPTZ DEFAULT NOW()
      );

      CREATE TABLE IF NOT EXISTS opencode_messages (
        id          TEXT PRIMARY KEY,
        session_id  TEXT REFERENCES opencode_sessions(id) ON DELETE CASCADE,
        role        TEXT,
        content     TEXT,
        model       TEXT,
        created_at  TIMESTAMPTZ,
        synced_at   TIMESTAMPTZ DEFAULT NOW()
      );

      CREATE TABLE IF NOT EXISTS opencode_stats (
        id              SERIAL PRIMARY KEY,
        recorded_at     TIMESTAMPTZ DEFAULT NOW(),
        total_sessions  INT,
        total_messages  INT,
        models_used     JSONB
      );

      CREATE INDEX IF NOT EXISTS idx_messages_session ON opencode_messages(session_id);
      CREATE INDEX IF NOT EXISTS idx_messages_created ON opencode_messages(created_at DESC);
      CREATE INDEX IF NOT EXISTS idx_sessions_updated ON opencode_sessions(updated_at DESC);
    `);
    console.log('[sync] ✓ Tablas PostgreSQL verificadas/creadas');
  } finally {
    client.release();
  }
}

// ── Leer sesiones desde SQLite usando opencode db ──────────
async function readOpencodeData() {
  const { execSync } = await import('child_process');
  const ocBin = process.platform === 'win32'
    ? path.join(__dirname, 'bin', 'opencode.exe')
    : 'opencode';

  try {
    // Leer sesiones (esquema real de OpenCode 1.17)
    const sessionsRaw = execSync(
      `"${ocBin}" db --format json "SELECT id, title, model FROM session LIMIT 500"`,
      { encoding: 'utf8', timeout: 10000, maxBuffer: 1024 * 1024 * 50 }
    ).trim();

    // Leer mensajes usando esquema real: id, session_id, time_created, data (JSON blob)
    const messagesRaw = execSync(
      `"${ocBin}" db --format json "SELECT id, session_id, time_created, data FROM message ORDER BY time_created DESC LIMIT 2000"`,
      { encoding: 'utf8', timeout: 10000, maxBuffer: 1024 * 1024 * 50 }
    ).trim();

    const sessions = sessionsRaw ? JSON.parse(sessionsRaw) : [];
    const rawMessages = messagesRaw ? JSON.parse(messagesRaw) : [];

    // Asignar timestamps artificiales a sesiones
    sessions.forEach(s => {
      s.created_at = new Date().toISOString();
      s.updated_at = s.created_at;
    });

    // Extraer role y content del campo JSON 'data'
    const messages = rawMessages.map(m => {
      let dataObj = {};
      try { dataObj = typeof m.data === 'string' ? JSON.parse(m.data) : (m.data || {}); } catch {}

      // Extraer content: puede ser string o array de partes
      let content = '';
      if (dataObj.content) {
        if (typeof dataObj.content === 'string') {
          content = dataObj.content;
        } else if (Array.isArray(dataObj.content)) {
          content = dataObj.content
            .filter(p => p && p.type === 'text')
            .map(p => p.text || '')
            .join('\n');
        }
      }

      return {
        id: m.id,
        session_id: m.session_id,
        role: dataObj.role || 'unknown',
        content: content,
        model: dataObj.modelID || null,
        created_at: m.time_created ? new Date(Number(m.time_created)).toISOString() : new Date().toISOString(),
      };
    });

    return { sessions, messages };
  } catch (err) {
    console.warn('[sync] \u26a0 No se pudo leer SQLite:', err.message);
    return { sessions: [], messages: [] };
  }
}

// ── Sincronizar datos a PostgreSQL ──────────────────────────
async function syncToPostgres() {
  console.log('[sync] 🔄 Iniciando sincronización...');
  const client = await pool.connect();
  try {
    const { sessions, messages } = await readOpencodeData();

    // Upsert sesiones
    for (const s of sessions) {
      await client.query(`
        INSERT INTO opencode_sessions (id, title, created_at, updated_at, model, synced_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (id) DO UPDATE SET
          title = EXCLUDED.title,
          updated_at = EXCLUDED.updated_at,
          model = EXCLUDED.model,
          synced_at = NOW()
      `, [s.id, s.title || 'Sin título', s.created_at, s.updated_at, s.model]);
    }

    // Upsert mensajes
    for (const m of messages) {
      try {
        await client.query(`
          INSERT INTO opencode_messages (id, session_id, role, content, model, created_at, synced_at)
          VALUES ($1, $2, $3, $4, $5, $6, NOW())
          ON CONFLICT (id) DO NOTHING
        `, [m.id, m.session_id, m.role, m.content, m.model, m.created_at]);
      } catch (err) {
        // Ignore foreign key violations (orphan messages from limited session queries)
        if (err.code !== '23503') {
          console.warn(`[sync] Warning inserting message ${m.id}:`, err.message);
        }
      }
    }

    // Guardar estadísticas
    const modelCount = messages.reduce((acc, m) => {
      if (m.model) acc[m.model] = (acc[m.model] || 0) + 1;
      return acc;
    }, {});

    await client.query(`
      INSERT INTO opencode_stats (total_sessions, total_messages, models_used)
      VALUES ($1, $2, $3)
    `, [sessions.length, messages.length, JSON.stringify(modelCount)]);

    console.log(`[sync] ✓ Sincronizadas ${sessions.length} sesiones, ${messages.length} mensajes`);
    return { sessions: sessions.length, messages: messages.length };
  } catch (err) {
    console.error('[sync] ✗ Error en sincronización:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

// ── API HTTP para consultar historial ───────────────────────
import http from 'http';

const API_PORT = parseInt(process.env.SYNC_API_PORT || '21295');

const apiServer = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${API_PORT}`);
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');

  try {
    if (url.pathname === '/api/sync' && req.method === 'POST') {
      const result = await syncToPostgres();
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, ...result }));

    } else if (url.pathname === '/api/sessions') {
      const limit = url.searchParams.get('limit') || 50;
      const { rows } = await pool.query(
        'SELECT * FROM opencode_sessions ORDER BY updated_at DESC LIMIT $1', [limit]
      );
      res.writeHead(200);
      res.end(JSON.stringify(rows));

    } else if (url.pathname.startsWith('/api/sessions/')) {
      const sessionId = url.pathname.split('/')[3];
      const { rows } = await pool.query(
        'SELECT * FROM opencode_messages WHERE session_id = $1 ORDER BY created_at ASC',
        [sessionId]
      );
      res.writeHead(200);
      res.end(JSON.stringify(rows));

    } else if (url.pathname === '/api/search') {
      const q = url.searchParams.get('q') || '';
      const { rows } = await pool.query(`
        SELECT m.*, s.title as session_title
        FROM opencode_messages m
        JOIN opencode_sessions s ON s.id = m.session_id
        WHERE m.content ILIKE $1
        ORDER BY m.created_at DESC LIMIT 50
      `, [`%${q}%`]);
      res.writeHead(200);
      res.end(JSON.stringify(rows));

    } else if (url.pathname === '/api/stats') {
      const { rows } = await pool.query(
        'SELECT * FROM opencode_stats ORDER BY recorded_at DESC LIMIT 1'
      );
      res.writeHead(200);
      res.end(JSON.stringify(rows[0] || {}));

    } else if (url.pathname === '/health') {
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, service: 'opencode-db-sync' }));

    } else {
      res.writeHead(404);
      res.end(JSON.stringify({ error: 'Not found' }));
    }
  } catch (err) {
    res.writeHead(500);
    res.end(JSON.stringify({ error: err.message }));
  }
});

// ── Inicio ───────────────────────────────────────────────────
async function main() {
  console.log('[sync] Conectando a PostgreSQL (EasyPanel)...');
  await pool.query('SELECT 1'); // test conexión
  console.log('[sync] ✓ Conectado a PostgreSQL');

  await initDatabase();

  // Sincronización inicial
  await syncToPostgres().catch(e => console.warn('[sync] Sync inicial omitida:', e.message));

  // Auto-sync cada 5 minutos
  setInterval(() => {
    syncToPostgres().catch(e => console.warn('[sync] Auto-sync falló:', e.message));
  }, 5 * 60 * 1000);

  // Levantar API
  apiServer.listen(API_PORT, '0.0.0.0', () => {
    console.log(`[sync] ✓ API de historial en http://localhost:${API_PORT}`);
    console.log(`[sync]   GET  /api/sessions         → todos los chats`);
    console.log(`[sync]   GET  /api/sessions/:id     → mensajes de un chat`);
    console.log(`[sync]   GET  /api/search?q=texto   → buscar en historial`);
    console.log(`[sync]   GET  /api/stats             → estadísticas`);
    console.log(`[sync]   POST /api/sync              → sincronizar ahora`);
  });
}

main().catch(err => {
  console.error('[sync] Error fatal:', err);
  process.exit(1);
});

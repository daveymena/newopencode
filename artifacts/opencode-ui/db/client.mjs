/**
 * OpenCode Evolved — Cliente de base de datos Supabase
 * Usando pg (PostgreSQL nativo) + Supabase JS client
 */
import pg from "pg";
import { createClient } from "@supabase/supabase-js";

const { Pool } = pg;

// ── Pool de PostgreSQL (para queries directas) ──
let pool = null;

export function getPool() {
  if (!pool) {
    const connStr = process.env.SUPABASE_DATABASE_URL;
    if (!connStr) {
      console.warn("⚠️  SUPABASE_DATABASE_URL no está configurado");
      return null;
    }
    pool = new Pool({
      connectionString: connStr,
      ssl: { rejectUnauthorized: false },
      max: 5,
      idleTimeoutMillis: 30000,
    });
    pool.on("error", (err) => {
      console.error("Pool error:", err.message);
    });
  }
  return pool;
}

// ── Cliente Supabase JS (para operaciones de alto nivel) ──
let supabase = null;

export function getSupabase() {
  if (!supabase) {
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!url || !key) {
      console.warn("⚠️  SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no están configurados");
      return null;
    }
    supabase = createClient(url, key, {
      auth: { persistSession: false },
    });
  }
  return supabase;
}

// ── Query helper ──
export async function query(sql, params = []) {
  const p = getPool();
  if (!p) return { rows: [] };
  try {
    const result = await p.query(sql, params);
    return result;
  } catch (err) {
    console.error("DB query error:", err.message, "\nSQL:", sql.slice(0, 100));
    return { rows: [] };
  }
}

// ── Operaciones de alto nivel ──

export const db = {
  // Sesiones
  async upsertSession({ oc_id, title, project_path, model, message_count }) {
    return query(
      `INSERT INTO sessions (oc_id, title, project_path, model, message_count)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (oc_id) DO UPDATE SET
         title = EXCLUDED.title,
         project_path = EXCLUDED.project_path,
         model = EXCLUDED.model,
         message_count = EXCLUDED.message_count,
         updated_at = NOW()
       RETURNING *`,
      [oc_id, title, project_path, model, message_count || 0]
    );
  },

  async getSessions(limit = 50) {
    return query(
      `SELECT s.*, p.name as project_name
       FROM sessions s
       LEFT JOIN projects p ON p.path = s.project_path
       ORDER BY s.updated_at DESC
       LIMIT $1`,
      [limit]
    );
  },

  // Memoria de IA
  async saveMemory(content) {
    const wordCount = content.split(/\s+/).filter(Boolean).length;
    return query(
      `INSERT INTO ai_memory (content, word_count)
       VALUES ($1, $2)
       ON CONFLICT DO NOTHING
       RETURNING *`,
      [content, wordCount]
    );
  },

  async getLatestMemory() {
    return query(
      `SELECT * FROM ai_memory ORDER BY updated_at DESC LIMIT 1`
    );
  },

  // Proyectos
  async upsertProject({ name, path, description, language }) {
    return query(
      `INSERT INTO projects (name, path, description, language)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (path) DO UPDATE SET
         last_opened = NOW(),
         session_count = projects.session_count + 1
       RETURNING *`,
      [name, path, description, language]
    );
  },

  async getProjects() {
    return query(
      `SELECT p.*, COUNT(s.id)::int as total_sessions
       FROM projects p
       LEFT JOIN sessions s ON s.project_path = p.path
       GROUP BY p.id
       ORDER BY p.last_opened DESC`
    );
  },

  // Configuración
  async getSetting(key) {
    const r = await query(`SELECT value FROM user_settings WHERE key = $1`, [key]);
    return r.rows[0]?.value;
  },

  async setSetting(key, value) {
    return query(
      `INSERT INTO user_settings (key, value)
       VALUES ($1, $2::jsonb)
       ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()`,
      [key, JSON.stringify(value)]
    );
  },

  // Stats
  async getStats() {
    const r = await query(`
      SELECT
        (SELECT COUNT(*) FROM sessions)::int as total_sessions,
        (SELECT COUNT(*) FROM messages)::int as total_messages,
        (SELECT COUNT(*) FROM projects)::int as total_projects,
        (SELECT SUM(tokens_in + tokens_out) FROM model_usage)::bigint as total_tokens
    `);
    return r.rows[0] || {};
  },
};

// ── Verificar conexión al iniciar ──
export async function checkConnection() {
  try {
    const r = await query("SELECT NOW() as time");
    if (r.rows.length > 0) {
      console.log("  ✓ Supabase conectado:", r.rows[0].time);
      return true;
    }
  } catch (e) {
    console.error("  ✗ Supabase no disponible:", e.message);
  }
  return false;
}

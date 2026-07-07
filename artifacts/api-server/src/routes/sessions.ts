import { Router, type IRouter } from "express";
import pg from "pg";

const { Pool } = pg;
const router: IRouter = Router();

// Pool lazy — se inicializa solo si DATABASE_URL está disponible
let pool: pg.Pool | null = null;
function getPool(): pg.Pool | null {
  if (!process.env.DATABASE_URL) return null;
  if (!pool) pool = new Pool({ connectionString: process.env.DATABASE_URL });
  return pool;
}

// GET /sessions
router.get("/sessions", async (req, res) => {
  const db = getPool();
  if (!db) { res.json({ sessions: [] }); return; }
  try {
    const { rows } = await db.query(
      `SELECT id, title, model,
              created_at  AS "createdAt",
              updated_at  AS "updatedAt"
       FROM opencode_sessions
       ORDER BY updated_at DESC NULLS LAST
       LIMIT 100`
    );
    res.json({ sessions: rows });
  } catch { res.json({ sessions: [] }); }
});

// POST /sessions
router.post("/sessions", async (req, res) => {
  const db = getPool();
  const { title, model } = req.body;
  const id = `session_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  const now = new Date().toISOString();

  if (db) {
    try {
      await db.query(
        `INSERT INTO opencode_sessions (id, title, model, created_at, updated_at)
         VALUES ($1, $2, $3, NOW(), NOW()) ON CONFLICT (id) DO NOTHING`,
        [id, title || "Nueva sesión", model || "claude-sonnet-4-6"]
      );
    } catch {}
  }

  res.status(201).json({
    id, title: title || "Nueva sesión",
    model: model || "claude-sonnet-4-6",
    createdAt: now, updatedAt: now,
  });
});

// GET /sessions/:sessionId
router.get("/sessions/:sessionId", async (req, res) => {
  const db = getPool();
  if (!db) { res.status(404).json({ error: "Session not found" }); return; }
  try {
    const { rows } = await db.query(
      `SELECT id, title, model, created_at AS "createdAt", updated_at AS "updatedAt"
       FROM opencode_sessions WHERE id = $1`,
      [req.params.sessionId]
    );
    if (!rows[0]) { res.status(404).json({ error: "Session not found" }); return; }
    res.json(rows[0]);
  } catch (err: any) { res.status(500).json({ error: err.message }); }
});

// DELETE /sessions/:sessionId
router.delete("/sessions/:sessionId", async (req, res) => {
  const db = getPool();
  if (db) {
    try { await db.query("DELETE FROM opencode_sessions WHERE id = $1", [req.params.sessionId]); }
    catch {}
  }
  res.status(204).send();
});

// GET /sessions/:sessionId/messages
router.get("/sessions/:sessionId/messages", async (req, res) => {
  const db = getPool();
  if (!db) { res.json({ messages: [] }); return; }
  try {
    const { rows } = await db.query(
      `SELECT id, session_id AS "sessionId", role, content, model,
              created_at AS "createdAt"
       FROM opencode_messages
       WHERE session_id = $1
       ORDER BY created_at ASC`,
      [req.params.sessionId]
    );
    res.json({ messages: rows });
  } catch { res.json({ messages: [] }); }
});

export default router;

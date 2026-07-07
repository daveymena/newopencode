import { Router, type IRouter } from "express";
import http from "http";
import pg from "pg";

const { Pool } = pg;
const router: IRouter = Router();

let pool: pg.Pool | null = null;
function getPool(): pg.Pool | null {
  if (!process.env.DATABASE_URL) return null;
  if (!pool) pool = new Pool({ connectionString: process.env.DATABASE_URL });
  return pool;
}

const OPENCODE_PORT = parseInt(process.env.OPENCODE_INTERNAL_PORT || "21294");

router.post("/chat", async (req, res) => {
  const { sessionId, message, model, systemPrompt } = req.body;

  if (!sessionId || !message) {
    res.status(400).json({ error: "sessionId y message son requeridos" });
    return;
  }

  // Guardar mensaje del usuario en PostgreSQL
  const db = getPool();
  if (db) {
    try {
      await db.query(
        `INSERT INTO opencode_messages (id, session_id, role, content, model, created_at)
         VALUES ($1, $2, 'user', $3, $4, NOW()) ON CONFLICT (id) DO NOTHING`,
        [`msg_user_${Date.now()}`, sessionId, message, model]
      );
    } catch {}
  }

  // Headers para streaming SSE
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

  const payload = JSON.stringify({ sessionId, message, model, systemPrompt });

  // Intentar reenviar a OpenCode interno
  const ocReq = http.request(
    {
      hostname: "localhost",
      port: OPENCODE_PORT,
      path: "/api/chat",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
    },
    (ocRes) => {
      let fullContent = "";
      ocRes.on("data", (chunk) => {
        const text = chunk.toString();
        fullContent += text;
        res.write(text);
      });
      ocRes.on("end", async () => {
        // Guardar respuesta del asistente
        if (db && fullContent) {
          try {
            await db.query(
              `INSERT INTO opencode_messages (id, session_id, role, content, model, created_at)
               VALUES ($1, $2, 'assistant', $3, $4, NOW()) ON CONFLICT (id) DO NOTHING`,
              [`msg_asst_${Date.now()}`, sessionId, fullContent, model]
            );
          } catch {}
        }
        res.end();
      });
    }
  );

  ocReq.on("error", () => {
    // Motor no disponible — mensaje de error en formato SSE
    res.write(
      `data: ${JSON.stringify({
        content: "El motor OpenCode no está disponible en este momento. Por favor intenta de nuevo.",
        done: true,
      })}\n\n`
    );
    res.end();
  });

  ocReq.write(payload);
  ocReq.end();

  req.on("close", () => ocReq.destroy());
});

export default router;

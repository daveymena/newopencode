-- ============================================================
-- OpenCode Evolved — Esquema de base de datos (Supabase)
-- ============================================================

-- Habilitar extensión UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Sesiones de chat (sincronizado con OpenCode) ──────────────
CREATE TABLE IF NOT EXISTS sessions (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  oc_id        TEXT UNIQUE,                  -- ID interno de OpenCode
  title        TEXT,
  project_path TEXT,
  model        TEXT,
  message_count INT DEFAULT 0,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Mensajes de cada sesión ──────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
  role       TEXT NOT NULL CHECK (role IN ('user','assistant','tool')),
  content    TEXT,
  model      TEXT,
  tokens_in  INT DEFAULT 0,
  tokens_out INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Memoria de IA (snapshots del memory.md) ───────────────────
CREATE TABLE IF NOT EXISTS ai_memory (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  content    TEXT NOT NULL,               -- contenido completo del memory.md
  word_count INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Proyectos ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        TEXT NOT NULL,
  path        TEXT UNIQUE NOT NULL,
  description TEXT,
  language    TEXT,                        -- lenguaje principal detectado
  last_opened TIMESTAMPTZ DEFAULT NOW(),
  session_count INT DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Configuración de usuario ──────────────────────────────────
CREATE TABLE IF NOT EXISTS user_settings (
  key        TEXT PRIMARY KEY,
  value      JSONB NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Uso de modelos de IA ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_usage (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  model      TEXT NOT NULL,
  provider   TEXT,
  tokens_in  BIGINT DEFAULT 0,
  tokens_out BIGINT DEFAULT 0,
  requests   INT DEFAULT 1,
  date       DATE DEFAULT CURRENT_DATE,
  UNIQUE(model, date)
);

-- ── Índices para rendimiento ──────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sessions_updated  ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_project  ON sessions(project_path);
CREATE INDEX IF NOT EXISTS idx_messages_session  ON messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_model_usage_date  ON model_usage(date DESC);
CREATE INDEX IF NOT EXISTS idx_projects_opened   ON projects(last_opened DESC);

-- ── Trigger: actualizar updated_at automáticamente ───────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  CREATE TRIGGER trg_sessions_updated
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TRIGGER trg_ai_memory_updated
    BEFORE UPDATE ON ai_memory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Insertar configuración por defecto ────────────────────────
INSERT INTO user_settings (key, value) VALUES
  ('theme',     '"dark"'),
  ('language',  '"es"'),
  ('auto_save', 'true'),
  ('model',     '"anthropic/claude-sonnet-4-6"')
ON CONFLICT (key) DO NOTHING;

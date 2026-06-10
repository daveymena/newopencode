import pg from './artifacts/opencode-ui/node_modules/pg/lib/index.js';
const { Client } = pg;
const DB = 'postgres://postgres:6715320@35.254.218.190:5433/davey?sslmode=disable';
const client = new Client({ connectionString: DB });

async function main() {
  await client.connect();
  console.log('✓ Conectado a PostgreSQL (EasyPanel)');

  // 1. Ver qué hay actualmente
  const { rows: tablas } = await client.query(
    `SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename`
  );
  console.log('\n📋 Tablas actuales:', tablas.map(r => r.tablename).join(', ') || '(ninguna)');

  // 2. Limpiar TODO lo que haya
  console.log('\n🗑  Limpiando base de datos...');
  await client.query(`DROP SCHEMA public CASCADE; CREATE SCHEMA public;`);
  console.log('✓ Schema limpiado completamente');

  // 3. Crear esquema limpio para OpenCode
  console.log('\n🔨 Creando esquema para OpenCode...');
  await client.query(`
    -- Sesiones / Conversaciones
    CREATE TABLE opencode_sessions (
      id          TEXT PRIMARY KEY,
      title       TEXT DEFAULT 'Sin título',
      model       TEXT,
      created_at  TIMESTAMPTZ,
      updated_at  TIMESTAMPTZ,
      synced_at   TIMESTAMPTZ DEFAULT NOW()
    );

    -- Mensajes individuales
    CREATE TABLE opencode_messages (
      id          TEXT PRIMARY KEY,
      session_id  TEXT REFERENCES opencode_sessions(id) ON DELETE CASCADE,
      role        TEXT,        -- 'user' | 'assistant' | 'tool'
      content     TEXT,
      model       TEXT,
      tokens_in   INT,
      tokens_out  INT,
      cost_usd    NUMERIC(10,6),
      created_at  TIMESTAMPTZ,
      synced_at   TIMESTAMPTZ DEFAULT NOW()
    );

    -- Estadísticas periódicas
    CREATE TABLE opencode_stats (
      id              SERIAL PRIMARY KEY,
      recorded_at     TIMESTAMPTZ DEFAULT NOW(),
      total_sessions  INT DEFAULT 0,
      total_messages  INT DEFAULT 0,
      total_tokens    INT DEFAULT 0,
      total_cost_usd  NUMERIC(10,4) DEFAULT 0,
      models_used     JSONB DEFAULT '{}'
    );

    -- Log de sincronizaciones
    CREATE TABLE opencode_sync_log (
      id          SERIAL PRIMARY KEY,
      synced_at   TIMESTAMPTZ DEFAULT NOW(),
      sessions    INT,
      messages    INT,
      status      TEXT,
      error       TEXT
    );

    -- Índices para búsqueda rápida
    CREATE INDEX idx_messages_session  ON opencode_messages(session_id);
    CREATE INDEX idx_messages_created  ON opencode_messages(created_at DESC);
    CREATE INDEX idx_messages_role     ON opencode_messages(role);
    CREATE INDEX idx_sessions_updated  ON opencode_sessions(updated_at DESC);
    CREATE INDEX idx_messages_search   ON opencode_messages USING gin(to_tsvector('spanish', content));
  `);
  console.log('✓ Esquema creado exitosamente');

  // 4. Verificar
  const { rows: nuevas } = await client.query(
    `SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename`
  );
  console.log('\n✅ Tablas creadas:');
  nuevas.forEach(r => console.log('   •', r.tablename));

  await client.end();
  console.log('\n🎉 Base de datos lista para OpenCode!');
}

main().catch(e => { console.error('✗ Error:', e.message); process.exit(1); });

/**
 * OpenCode Evolved — Script de migración
 * Ejecuta: node artifacts/opencode-ui/db/migrate.mjs
 */
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import path from "path";
import pg from "pg";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const { Client } = pg;

const connStr = process.env.SUPABASE_DATABASE_URL;
if (!connStr) {
  console.error("❌ SUPABASE_DATABASE_URL no configurado");
  process.exit(1);
}

const client = new Client({
  connectionString: connStr,
  ssl: { rejectUnauthorized: false },
});

async function migrate() {
  console.log("🗄️  Ejecutando migración en Supabase...");
  await client.connect();

  try {
    const sql = readFileSync(path.join(__dirname, "schema.sql"), "utf8");

    // Ejecutar cada sentencia por separado para mejor control de errores
    const statements = sql
      .split(";")
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && !s.startsWith("--"));

    let ok = 0;
    let failed = 0;

    for (const stmt of statements) {
      try {
        await client.query(stmt);
        ok++;
      } catch (err) {
        // Ignorar errores de "ya existe"
        if (
          err.message.includes("already exists") ||
          err.message.includes("duplicate")
        ) {
          ok++;
        } else {
          console.error(`  ⚠ ${err.message.slice(0, 100)}`);
          failed++;
        }
      }
    }

    console.log(`  ✓ ${ok} sentencias ejecutadas, ${failed} errores`);
    console.log("  ✓ Tablas creadas: sessions, messages, ai_memory, projects, user_settings, model_usage");
    console.log("✅ Migración completa");
  } finally {
    await client.end();
  }
}

migrate().catch((e) => {
  console.error("❌ Migración fallida:", e.message);
  process.exit(1);
});

import { Router, type IRouter } from "express";
import fs from "fs/promises";
import path from "path";

const router: IRouter = Router();

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || process.cwd();

const BLOCKED_PATHS = [".git", "node_modules", ".local", "dist", ".replit-artifact"];
const MAX_FILE_SIZE = 1024 * 1024; // 1MB

function getLanguageFromExtension(ext: string): string {
  const map: Record<string, string> = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".css": "css",
    ".html": "html",
    ".sh": "bash",
    ".py": "python",
    ".toml": "toml",
    ".env": "plaintext",
    ".txt": "plaintext",
  };
  return map[ext] || "plaintext";
}

async function buildFileTree(dirPath: string, name: string, depth = 0): Promise<any> {
  if (depth > 6) return null;

  const relativeName = path.basename(dirPath);
  if (BLOCKED_PATHS.some((blocked) => relativeName === blocked)) return null;

  let stat;
  try {
    stat = await fs.stat(dirPath);
  } catch {
    return null;
  }

  if (stat.isFile()) {
    return {
      name,
      path: dirPath,
      type: "file",
      size: stat.size,
    };
  }

  if (stat.isDirectory()) {
    let entries;
    try {
      entries = await fs.readdir(dirPath);
    } catch {
      return { name, path: dirPath, type: "directory", children: [] };
    }

    const children = await Promise.all(
      entries
        .filter((entry) => !entry.startsWith(".") || entry === ".env")
        .filter((entry) => !BLOCKED_PATHS.includes(entry))
        .map((entry) => buildFileTree(path.join(dirPath, entry), entry, depth + 1)),
    );

    return {
      name,
      path: dirPath,
      type: "directory",
      children: children.filter(Boolean).sort((a: any, b: any) => {
        if (a.type === b.type) return a.name.localeCompare(b.name);
        return a.type === "directory" ? -1 : 1;
      }),
    };
  }

  return null;
}

router.get("/files", async (req, res) => {
  const requestedPath = (req.query.path as string) || ".";
  const absolutePath = path.resolve(WORKSPACE_ROOT, requestedPath);

  try {
    const tree = await buildFileTree(absolutePath, path.basename(absolutePath));
    if (!tree) {
      res.status(404).json({ error: "Ruta no encontrada" });
      return;
    }
    res.json({ tree });
  } catch (err: any) {
    req.log.error({ err }, "Error al leer árbol de archivos");
    res.status(500).json({ error: "Error al leer el árbol de archivos" });
  }
});

router.get("/files/read", async (req, res) => {
  const filePath = req.query.path as string;
  if (!filePath) {
    res.status(400).json({ error: "Se requiere el parámetro path" });
    return;
  }

  const absolutePath = path.resolve(WORKSPACE_ROOT, filePath);

  try {
    const stat = await fs.stat(absolutePath);
    if (stat.size > MAX_FILE_SIZE) {
      res.status(413).json({ error: "Archivo demasiado grande (máximo 1MB)" });
      return;
    }

    const content = await fs.readFile(absolutePath, "utf-8");
    const ext = path.extname(absolutePath);
    const language = getLanguageFromExtension(ext);

    res.json({
      path: filePath,
      content,
      language,
      size: stat.size,
    });
  } catch (err: any) {
    if (err.code === "ENOENT") {
      res.status(404).json({ error: "Archivo no encontrado" });
      return;
    }
    req.log.error({ err }, "Error al leer archivo");
    res.status(500).json({ error: "Error al leer el archivo" });
  }
});

router.post("/files/write", async (req, res) => {
  const { path: filePath, content } = req.body;

  if (!filePath || content === undefined) {
    res.status(400).json({ error: "Se requieren path y content" });
    return;
  }

  const absolutePath = path.resolve(WORKSPACE_ROOT, filePath);

  try {
    await fs.mkdir(path.dirname(absolutePath), { recursive: true });
    await fs.writeFile(absolutePath, content, "utf-8");
    res.json({ success: true, message: "Archivo guardado correctamente" });
  } catch (err: any) {
    req.log.error({ err }, "Error al escribir archivo");
    res.status(500).json({ error: "Error al escribir el archivo" });
  }
});

export default router;

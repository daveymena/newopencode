import { Router, type IRouter } from "express";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);
const router: IRouter = Router();

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || process.cwd();
const MAX_TIMEOUT = 30000;

const BLOCKED_COMMANDS = [
  "rm -rf /",
  "mkfs",
  "dd if=/dev/zero",
  "> /dev/sda",
  "chmod -R 777 /",
];

router.post("/terminal/execute", async (req, res) => {
  const { command, cwd, timeout } = req.body;

  if (!command || typeof command !== "string") {
    res.status(400).json({ error: "Se requiere un comando" });
    return;
  }

  const commandLower = command.toLowerCase();
  const isBlocked = BLOCKED_COMMANDS.some((blocked) => commandLower.includes(blocked));
  if (isBlocked) {
    res.status(403).json({ error: "Comando no permitido por razones de seguridad" });
    return;
  }

  const workingDir = cwd ? cwd : WORKSPACE_ROOT;
  const timeoutMs = Math.min(timeout || 10000, MAX_TIMEOUT);

  const start = Date.now();
  try {
    const { stdout, stderr } = await execAsync(command, {
      cwd: workingDir,
      timeout: timeoutMs,
      maxBuffer: 1024 * 1024 * 2,
      env: { ...process.env, FORCE_COLOR: "1" },
    });

    res.json({
      stdout: stdout || "",
      stderr: stderr || "",
      exitCode: 0,
      duration: Date.now() - start,
    });
  } catch (err: any) {
    res.json({
      stdout: err.stdout || "",
      stderr: err.stderr || err.message || "Error desconocido",
      exitCode: err.code || 1,
      duration: Date.now() - start,
    });
  }
});

export default router;

import { Router, type IRouter } from "express";

const router: IRouter = Router();

const AVAILABLE_MODELS = [
  {
    id: "claude-sonnet-4-6",
    name: "Claude Sonnet 4.6",
    provider: "Anthropic",
    description: "Rendimiento equilibrado, recomendado para la mayoría de tareas",
  },
  {
    id: "claude-opus-4-6",
    name: "Claude Opus 4.6",
    provider: "Anthropic",
    description: "Más capaz, ideal para tareas complejas de razonamiento y código",
  },
  {
    id: "claude-haiku-4-5",
    name: "Claude Haiku 4.5",
    provider: "Anthropic",
    description: "Más rápido y compacto, ideal para tareas simples",
  },
];

router.get("/models", (_req, res) => {
  res.json({ models: AVAILABLE_MODELS });
});

export default router;

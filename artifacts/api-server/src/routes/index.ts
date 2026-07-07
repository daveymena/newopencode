import { Router, type IRouter } from "express";
import healthRouter from "./health";
import modelsRouter from "./models";
import filesRouter from "./files";
import terminalRouter from "./terminal";
import sessionsRouter from "./sessions";
import chatRouter from "./chat";

const router: IRouter = Router();

router.use(healthRouter);
router.use(modelsRouter);
router.use(filesRouter);
router.use(terminalRouter);
router.use(sessionsRouter);
router.use(chatRouter);

export default router;

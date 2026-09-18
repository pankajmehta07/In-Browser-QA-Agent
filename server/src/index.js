import path from "node:path";
import express from "express";
import cors from "cors";
import { fileURLToPath } from "node:url";

import healthRouter    from "./routers/health.js";
import runsRouter      from "./routers/runs.js";
import testsRouter     from "./routers/tests.js";
import approvalsRouter from "./routers/approvals.js";

const app = express();
const port = 4000;

const currentFilePath = fileURLToPath(import.meta.url);
const currentDirectory = path.dirname(currentFilePath);
const screenshotsDirectory = path.join(currentDirectory, "..", "data", "screenshots");

app.use(cors());
app.use(express.json());
app.use("/screenshots", express.static(screenshotsDirectory));

app.use(healthRouter);
app.use(runsRouter);
app.use(testsRouter);
app.use(approvalsRouter);

app.listen(port, () => {
  console.log(`QA Agent server running at http://127.0.0.1:${port}`);
});

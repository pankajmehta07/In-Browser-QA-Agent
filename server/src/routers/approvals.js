import { Router } from "express";
import { listApprovals, saveApproval } from "../approvalStore.js";

const router = Router();

router.get("/approvals", async (request, response) => {
  try {
    const approvals = await listApprovals();
    response.json(approvals);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message
    });
  }
});

router.post("/approvals", async (request, response) => {
  try {
    const {
      runId,
      stepName,
      oldSelector,
      newSelector,
      oldTarget,
      newTarget,
      decision,
      confidence,
      strategy
    } = request.body;

    if (!runId || !stepName || !decision) {
      response.status(400).json({
        status: "failed",
        errorMessage: "runId, stepName, and decision are required"
      });
      return;
    }

    const savedApproval = await saveApproval({
      runId,
      stepName,
      oldSelector,
      newSelector,
      oldTarget,
      newTarget,
      decision,
      confidence,
      strategy
    });

    response.json(savedApproval);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message
    });
  }
});


export default router;
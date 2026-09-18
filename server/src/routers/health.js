import { Router } from "express";

const router = Router();

router.get("/health", (request, response) => {
    response.json({
        ok: true,
        service: "in-browser-qa-agent-server",
    });
});

export default router;
import { Router } from "express";
import { deleteTest, listTests, saveTest } from "../testStore.js";

const router = Router();

router.get("/tests", async (request, response) => {
    try {
        const tests = await listTests();
        response.json(tests);
    } catch (error) {
        response.status(500).json({
            status: "failed",
            errorMessage: error.message,
        });
    }
});

router.post("/tests", async (request, response) => {
    try {
        const { name, instruction, variant = "original", reruns = 1 } = request.body;

        if (!name || !instruction) {
            response.status(400).json({
                status: "failed",
                errorMessage: "name and instruction are required",
            });
            return;
        }

        const savedTest = await saveTest({ name, instruction, variant, reruns });
        response.json(savedTest);
    } catch (error) {
        response.status(500).json({
            status: "failed",
            errorMessage: error.message,
        });
    }
});

router.delete("/tests/:id", async (request, response) => {
    try {
        const deleted = await deleteTest(request.params.id);

        if (!deleted) {
            response.status(404).json({
                status: "failed",
                errorMessage: "Test not found",
            });
            return;
        }

        response.json({
            status: "passed",
            deletedId: request.params.id,
        });
    } catch (error) {
        response.status(500).json({
            status: "failed",
            errorMessage: error.message,
        });
    }
});

export default router;
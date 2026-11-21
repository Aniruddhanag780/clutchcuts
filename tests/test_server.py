import threading
import time
import unittest
from unittest.mock import patch

from web_app import server


class GenerateEndpointTests(unittest.TestCase):
    def setUp(self):
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        with server.JOB_LOCK:
            server.STATE.update({
                "is_running": False,
                "progress": 0,
                "status_message": "Ready to generate shorts",
                "logs": [],
                "current_results": [],
                "error": None,
            })

    def test_rejects_malformed_request_and_invalid_url(self):
        self.assertEqual(self.client.post("/api/generate").status_code, 400)
        response = self.client.post("/api/generate", json={"url": "not a URL"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("http://", response.get_json()["error"])

    def test_rejects_unsupported_clip_count(self):
        response = self.client.post(
            "/api/generate",
            json={"url": "https://www.youtube.com/watch?v=example", "clip_count": "4"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("1, 2, 3, or 5", response.get_json()["error"])

    def test_only_allows_one_generation_job_at_a_time(self):
        started = threading.Event()
        release = threading.Event()

        def wait_for_release(*args, **kwargs):
            started.set()
            release.wait(timeout=2)
            return []

        try:
            with patch.object(server.pipeline_engine, "process_stream", side_effect=wait_for_release):
                payload = {"url": "https://www.youtube.com/watch?v=example", "clip_count": 1}
                self.assertEqual(self.client.post("/api/generate", json=payload).status_code, 200)
                self.assertTrue(started.wait(timeout=1))
                conflict = self.client.post("/api/generate", json=payload)
                self.assertEqual(conflict.status_code, 409)
        finally:
            release.set()
            deadline = time.time() + 2
            while server.STATE["is_running"] and time.time() < deadline:
                time.sleep(0.01)


if __name__ == "__main__":
    unittest.main()

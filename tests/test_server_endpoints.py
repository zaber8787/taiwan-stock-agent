# File: tests/test_server_endpoints.py

import unittest
from fastapi.testclient import TestClient
from app.server import app

class TestServerEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_notify_status_endpoint(self):
        response = self.client.get("/api/notify/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("enabled", data)
        self.assertIn("configured", data)

    def test_notify_test_endpoint_unconfigured(self):
        response = self.client.post("/api/notify/test")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("success", data)
        self.assertIn("message", data)


if __name__ == '__main__':
    unittest.main()

from __future__ import annotations

import httpx


class ServerClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def request(self, method: str, endpoint: str, payload: dict | None = None):
        with httpx.Client(base_url=self.base_url, headers=self.headers, timeout=30) as client:
            response = client.request(method, endpoint, json=payload)
            response.raise_for_status()
            return response.json()

    def manifest(self): return self.request("GET", "/api/v1/xhs-agent/manifest")
    def heartbeat(self, payload): return self.request("POST", "/api/v1/xhs-agent/heartbeat", payload)
    def create_batch(self, payload): return self.request("POST", "/api/v1/xhs-agent/batches", payload)
    def progress(self, batch_id: str, payload): return self.request("PATCH", f"/api/v1/xhs-agent/batches/{batch_id}/progress", payload)
    def upload(self, batch_id: str, payload): return self.request("POST", f"/api/v1/xhs-agent/batches/{batch_id}/results", payload)
    def command_status(self, command_id: str, payload): return self.request("POST", f"/api/v1/xhs-agent/commands/{command_id}/status", payload)

#!/usr/bin/env python3
"""Smoke-test a local or deployed private-alpha API.

The smoke path uses mock-safe endpoints and never requires paid providers.
This script is intentionally stored as real LF-delimited text in Git.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any


@dataclass
class ApiResponse:
    status: int
    data: Any
    raw: bytes


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, payload: Any | None = None, *, accept_binary: bool = False) -> ApiResponse:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["X-Alpha-Token"] = self.token
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read()
                if accept_binary:
                    return ApiResponse(response.status, None, raw)
                return ApiResponse(response.status, json.loads(raw.decode("utf-8") or "{}"), raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            parsed: Any
            try:
                parsed = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                parsed = raw.decode("utf-8", errors="replace")
            return ApiResponse(exc.code, parsed, raw)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a private-alpha API smoke test without real providers.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL.")
    parser.add_argument("--admin-token", required=True, help="ALPHA_ADMIN_TOKEN value.")
    parser.add_argument("--tester-a-token", required=True, help="Tester A alpha token.")
    parser.add_argument("--tester-b-token", help="Tester B alpha token for isolation checks.")
    args = parser.parse_args()

    public = ApiClient(args.base_url)
    admin = ApiClient(args.base_url, args.admin_token)
    tester_a = ApiClient(args.base_url, args.tester_a_token)
    tester_b = ApiClient(args.base_url, args.tester_b_token) if args.tester_b_token else None

    health = public.request("GET", "/health")
    require(health.status == 200 and health.data.get("status") == "ok", "health endpoint failed")
    print("PASS health")

    readiness = admin.request("GET", "/alpha/readiness")
    require(readiness.status == 200, f"alpha readiness failed: {readiness.data}")
    require(readiness.data.get("ready") is True, f"alpha readiness is not ready: {readiness.data.get('checks')}")
    print("PASS alpha readiness")

    onboarding = public.request("GET", "/alpha/onboarding")
    require(onboarding.status == 200, "alpha onboarding failed")
    print("PASS onboarding")

    demo = tester_a.request("POST", "/demo/create-full-project", {})
    require(demo.status == 201, f"demo creation failed: {demo.data}")
    project_id = demo.data["project"]["id"]
    print(f"PASS demo project {project_id}")

    own_projects = tester_a.request("GET", "/projects")
    require(own_projects.status == 200 and any(project["id"] == project_id for project in own_projects.data), "tester A project listing failed")
    print("PASS tester project list")

    if tester_b:
        blocked = tester_b.request("GET", f"/projects/{project_id}")
        require(blocked.status in {403, 404}, "tester B could access tester A project")
        print("PASS tester isolation")

    exports = demo.data.get("exports", {})
    export_id = next(iter(exports.values()), None)
    require(export_id, "demo did not create an export")
    download = tester_a.request("GET", f"/exports/{export_id}/download", accept_binary=True)
    require(download.status == 200 and len(download.raw) > 0, "export download failed")
    print("PASS export download")

    print("Alpha smoke test passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)

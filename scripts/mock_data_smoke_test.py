#!/usr/bin/env python3
"""Read-only production smoke checks for the Samora mock-data API.

Required environment:
  SAMORA_API_URL   Base URL of the deployed FastAPI service
  SAMORA_API_KEY   Server-side API key (never printed)

Run:
  python scripts/mock_data_smoke_test.py

The script performs GET requests only. It does not seed data, run pipelines,
train models, import BancABC exports, or mutate database records.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Check:
    name: str
    path: str
    requires_key: bool = True


CHECKS = (
    Check("Backend health", "/health", False),
    Check("Executive overview", "/api/v1/executive/overview?period_days=30"),
    Check("Executive transactions", "/api/v1/executive/transactions"),
    Check("Growth intelligence overview", "/api/v1/growth/overview"),
    Check("Development segmentation profile", "/api/v1/model-training/development-segmentation/profile"),
)


def request_json(base_url: str, api_key: str, check: Check, timeout: float) -> tuple[int, Any, float]:
    headers = {"Accept": "application/json", "User-Agent": "samora-mock-readiness-smoke/1.0"}
    if check.requires_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(base_url + check.path, headers=headers, method="GET")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            elapsed = (time.monotonic() - started) * 1000
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("response was not valid JSON") from exc
            return response.status, body, elapsed
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = {"error": "non-JSON error response"}
        return exc.code, body, (time.monotonic() - started) * 1000


def main() -> int:
    base_url = os.getenv("SAMORA_API_URL", "").strip().rstrip("/")
    api_key = os.getenv("SAMORA_API_KEY", "").strip()
    timeout = float(os.getenv("SAMORA_SMOKE_TIMEOUT_SECONDS", "20"))

    if not base_url:
        print("CONFIG ERROR: SAMORA_API_URL is required.")
        return 2
    if not api_key:
        print("CONFIG ERROR: SAMORA_API_KEY is required for authenticated checks.")
        return 2
    if not base_url.startswith(("https://", "http://")):
        print("CONFIG ERROR: SAMORA_API_URL must be an HTTP(S) URL.")
        return 2

    failures = 0
    print("Samora Ledger Tech — read-only mock-data API smoke test")
    print(f"Target: {base_url}")
    print("No customer data, credentials, or response bodies will be printed.")
    print()

    for check in CHECKS:
        try:
            status, body, elapsed = request_json(base_url, api_key, check, timeout)
            valid_json_object = isinstance(body, dict)
            ok = 200 <= status < 300 and valid_json_object
            detail = "valid JSON object" if valid_json_object else "expected a JSON object"
            if isinstance(body, dict) and status >= 400:
                detail = str(body.get("detail") or body.get("error") or f"HTTP {status}")
            print(f"{'PASS' if ok else 'FAIL'}  {check.name}: HTTP {status}, {elapsed:.0f} ms — {detail}")
            failures += not ok
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"FAIL  {check.name}: {type(exc).__name__}: {exc}")
            failures += 1

    print()
    print(f"Result: {len(CHECKS) - failures}/{len(CHECKS)} checks passed.")
    if failures:
        print("Readiness is not verified. Investigate failing endpoints before closing Phase 2.")
        return 1
    print("Read-only endpoint availability verified. This does not validate business correctness or production approval.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

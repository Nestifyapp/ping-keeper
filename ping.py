import os
import sys
import time
import uuid
import logging
from datetime import datetime, timezone

import requests

# =========================================================
# CONFIG
# =========================================================

ENDPOINTS = [
    {
        "name": "bluedome",
        "url": "https://bluedome.onrender.com/health",
        "enabled": True,
    },
    {
        "name": "equity-payments",
        "url": "https://equity-payments-production.up.railway.app/health",
        "enabled": True,
    },
    {
        "name": "mpesa-sdk-backend",
        "url": "https://mpesa-sdk-backend.onrender.com/health",
        "enabled": True,
    },
    {
        "name": "jemmy-coaching",
        "url": "https://jemmy-coaching-and-leadership.web.app/health",
        "enabled": True,
    },
]

TIMEOUT_SECONDS = 10
RETRIES = 2
DELAY_BETWEEN_ENDPOINTS_SECONDS = 2
FAIL_ON_ERROR = False  # Set to True if you want GitHub Action to fail when any endpoint fails.

# Optional secret header if one day you protect your health endpoint
HEALTH_TOKEN = os.getenv("HEALTH_TOKEN")

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("endpoint_pinger")


# =========================================================
# HELPERS
# =========================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_headers(request_id: str) -> dict:
    headers = {
        "User-Agent": "github-actions-endpoint-warmer/1.0",
        "X-Warm-Request-Id": request_id,
    }

    if HEALTH_TOKEN:
        headers["X-Health-Token"] = HEALTH_TOKEN

    return headers


def ping_endpoint(session: requests.Session, endpoint: dict, request_id: str) -> dict:
    name = endpoint["name"]
    url = endpoint["url"]
    headers = build_headers(request_id)

    for attempt in range(1, RETRIES + 1):
        started_at = time.perf_counter()

        try:
            logger.info(
                "ping_start request_id=%s name=%s url=%s attempt=%s",
                request_id,
                name,
                url,
                attempt,
            )

            response = session.get(url, timeout=TIMEOUT_SECONDS, headers=headers)

            duration_seconds = round(time.perf_counter() - started_at, 3)
            ok = 200 <= response.status_code < 500

            logger.info(
                "ping_done request_id=%s name=%s status_code=%s ok=%s duration_seconds=%s",
                request_id,
                name,
                response.status_code,
                ok,
                duration_seconds,
            )

            return {
                "name": name,
                "url": url,
                "ok": ok,
                "status_code": response.status_code,
                "attempt": attempt,
                "duration_seconds": duration_seconds,
                "checked_at": utc_now_iso(),
            }

        except requests.RequestException as e:
            duration_seconds = round(time.perf_counter() - started_at, 3)

            logger.warning(
                "ping_error request_id=%s name=%s attempt=%s duration_seconds=%s error=%s",
                request_id,
                name,
                attempt,
                duration_seconds,
                str(e),
            )

            if attempt < RETRIES:
                time.sleep(2)
            else:
                return {
                    "name": name,
                    "url": url,
                    "ok": False,
                    "error": str(e),
                    "attempt": attempt,
                    "duration_seconds": duration_seconds,
                    "checked_at": utc_now_iso(),
                }


def main() -> int:
    request_id = str(uuid.uuid4())
    logger.info("warm_run_started request_id=%s", request_id)

    enabled_endpoints = [ep for ep in ENDPOINTS if ep.get("enabled", True)]

    if not enabled_endpoints:
        logger.warning("no_enabled_endpoints request_id=%s", request_id)
        return 0

    results = []
    failed_count = 0

    with requests.Session() as session:
        for index, endpoint in enumerate(enabled_endpoints):
            result = ping_endpoint(session, endpoint, request_id)
            results.append(result)

            if not result.get("ok", False):
                failed_count += 1

            # Delay between endpoints, but not after the last one
            if index < len(enabled_endpoints) - 1:
                time.sleep(DELAY_BETWEEN_ENDPOINTS_SECONDS)

    success_count = len(results) - failed_count

    logger.info(
        "warm_run_completed request_id=%s total=%s success=%s failed=%s",
        request_id,
        len(results),
        success_count,
        failed_count,
    )

    print("\n===== SUMMARY =====")
    print(f"request_id: {request_id}")
    print(f"total: {len(results)}")
    print(f"success: {success_count}")
    print(f"failed: {failed_count}")

    for result in results:
        if result.get("ok"):
            print(
                f"[OK] {result['name']} -> {result.get('status_code')} "
                f"(attempt={result.get('attempt')}, duration={result.get('duration_seconds')}s)"
            )
        else:
            print(
                f"[FAIL] {result['name']} -> {result.get('error', 'unknown error')} "
                f"(attempt={result.get('attempt')}, duration={result.get('duration_seconds')}s)"
            )

    if FAIL_ON_ERROR and failed_count > 0:
        logger.error("warm_run_failed request_id=%s because one or more endpoints failed", request_id)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

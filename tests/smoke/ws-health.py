#!/usr/bin/env python3
"""WebSocket smoke test — verifies WS connectivity through the dashboard proxy.

Usage:
    python ws-health.py
    python ws-health.py --url ws://localhost:3001/ws --token <api_key>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import websockets


async def smoke_test(url: str, token: str | None, timeout: float = 5.0) -> bool:
    ws_url = url
    if token:
        sep = "&" if "?" in ws_url else "?"
        ws_url = f"{ws_url}{sep}api_key={token}"

    print(f"Connecting to {url} ...")
    async with websockets.connect(ws_url, open_timeout=timeout) as ws:
        print("Connected.")

        # 1. Ping / pong — verifies WS connectivity and proxying
        await ws.send(json.dumps({"action": "ping"}))
        print("Sent: ping")

        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        resp = json.loads(raw)
        print(f"Received: {resp}")

        if resp.get("type") != "pong":
            print(f"FAIL: expected type 'pong', got '{resp.get('type')}'")
            return False

        # 2. Subscribe — verifies auth token forwarding and message routing
        #    Uses a dummy meeting; expect either 'subscribed' or auth error.
        #    Both prove the full WS path works. Only a connection failure is a FAIL.
        subscribe_msg = {
            "action": "subscribe",
            "meetings": [{"platform": "google_meet", "native_id": "smoke-test"}],
        }
        await ws.send(json.dumps(subscribe_msg))
        print("Sent: subscribe")

        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        resp = json.loads(raw)
        print(f"Received: {resp}")

        if resp.get("type") == "subscribed":
            print("PASS: ping/pong + subscribe OK")
        elif resp.get("type") == "error":
            # Auth/meeting errors prove the WS path works end-to-end
            print(f"PASS: ping/pong OK, subscribe returned expected error: {resp.get('error')}")
        else:
            print(f"FAIL: unexpected response type '{resp.get('type')}'")
            return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket smoke test")
    parser.add_argument(
        "--url",
        default=os.environ.get("WS_URL", "ws://localhost:3001/ws"),
        help="WebSocket URL (default: ws://localhost:3001/ws)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("VEXA_API_KEY"),
        help="API key for authentication (default: $VEXA_API_KEY)",
    )
    args = parser.parse_args()

    try:
        ok = asyncio.run(smoke_test(args.url, args.token))
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

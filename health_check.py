#!/usr/bin/env python3
import httpx
import sys

async def check():
    try:
        r = httpx.get("http://localhost:8080/health", timeout=5)
        if r.status_code == 200:
            print("OK")
            sys.exit(0)
    except:
        pass
    print("FAIL")
    sys.exit(1)

import asyncio
asyncio.run(check())
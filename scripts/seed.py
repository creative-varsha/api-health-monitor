"""Register the 4 demo endpoints through the running API.

Usage: python scripts/seed.py http://localhost:8000
"""
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

SERVICES = [
    {"name": "GitHub API", "url": "https://api.github.com"},
    {"name": "JSONPlaceholder", "url": "https://jsonplaceholder.typicode.com/posts/1"},
    {"name": "HTTPBin OK", "url": "https://httpbin.org/status/200"},
    {"name": "HTTPBin Always Fails (demo incident)", "url": "https://httpbin.org/status/503"},
]

for svc in SERVICES:
    r = httpx.post(f"{BASE}/services", json=svc, timeout=15)
    print(svc["name"], "->", r.status_code, r.text[:100])

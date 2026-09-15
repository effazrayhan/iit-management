import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

URL = os.getenv("LOAD_TEST_URL", "http://localhost:8000/api/health")
REQUESTS = int(os.getenv("LOAD_TEST_REQUESTS", "100"))
CONCURRENCY = int(os.getenv("LOAD_TEST_CONCURRENCY", "10"))


def hit(_):
    with urlopen(URL, timeout=10) as response:
        return response.status


started = time.perf_counter()
with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
    statuses = list(pool.map(hit, range(REQUESTS)))
elapsed = time.perf_counter() - started
assert all(status == 200 for status in statuses)
print(f"{REQUESTS} requests in {elapsed:.2f}s ({REQUESTS / elapsed:.1f} req/s)")

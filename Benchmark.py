import time
from contextlib import contextmanager


# --------------------------------------------------
# Benchmarking
# --------------------------------------------------

@contextmanager
def benchmark(name):
    start = time.perf_counter()

    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"[BENCHMARK] {name:<35} {elapsed:9.3f}s")

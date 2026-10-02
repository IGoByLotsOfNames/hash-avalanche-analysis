# Benchmark method

```bash
python tools/benchmark.py --sizes 1000 10000 100000 --repeats 3 --seed 20261002 --output benchmarks/my-run.json
```

The script runs both algorithms with identical seeded payloads in streaming and retained modes. It checks exact histogram/moment fingerprints for every pair. The retained reference mirrors the old per-trial list-to-tuple storage strategy, then constructs a histogram and moments. It is a small controlled reference, not a rerun of historical notebook/essay code or the ten-million-trial investigation.

For each configuration, a fresh worker process records three **untraced** experiment runtimes. It then separately runs tracemalloc to measure peak Python allocation. Runtime includes aggregate construction but excludes child-process startup, imports and input/output. Memory includes the result and transient Python allocations, but excludes native OpenSSL allocations and total process RSS. Tracemalloc timings are not mixed into the runtime table. Garbage collection occurs before each measurement; no best-of selection or removed warm-up is used.

The JSON records every sample, platform, Python version, CPU identifier, seed, payload size, source hash, memory scope and output fingerprint. Host scheduling and other work can affect timings, so interpret trends and do not generalise a single machine's ratios. Streaming can be slower for small experiments due to per-trial aggregation overhead.

The primary claim is asymptotic storage: fixed bins and scalar counters replace N retained observations. Bin/counter integer bit widths still grow with the count. The observed trace peak need not be identical at every N because additional bins become occupied and integer objects cross size thresholds.

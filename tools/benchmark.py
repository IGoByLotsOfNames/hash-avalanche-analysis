"""Compare bounded aggregates with a retained-distance reference on identical trials."""
from __future__ import annotations
import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hash_avalanche.experiment import flip_one_bit, hamming_distance, run_experiment


def retained(algorithm, trials, payload_bytes, seed):
    rng = random.Random(seed)
    distances = []
    for _ in range(trials):
        payload = rng.getrandbits(payload_bytes * 8).to_bytes(payload_bytes, 'little')
        modified = flip_one_bit(payload, rng.randrange(payload_bytes * 8))
        distances.append(hamming_distance(hashlib.new(algorithm, payload, usedforsecurity=False).digest(),
                                          hashlib.new(algorithm, modified, usedforsecurity=False).digest()))
    values = tuple(distances)
    return {'distribution': dict(Counter(values)), 'sum': sum(values),
            'squares': sum(x*x for x in values), 'retained_distances': values}


def measure(args):
    def run():
        if args.mode == 'retained':
            return retained(args.algorithm, args.trials, args.payload_bytes, args.seed)
        result = run_experiment(args.algorithm, trials=args.trials, payload_bytes=args.payload_bytes, seed=args.seed)
        return {'distribution': result.distribution, 'sum': result.distance_sum, 'squares': result.distance_square_sum}
    times = []
    for _ in range(args.repeats):
        gc.collect()
        start = time.perf_counter()
        result = run()
        times.append(time.perf_counter() - start)
        del result
    gc.collect()
    tracemalloc.start()
    result = run()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result.pop('retained_distances', None)
    fingerprint = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return {'algorithm': args.algorithm, 'trials': args.trials, 'mode': args.mode,
            'seconds': times, 'median_seconds': statistics.median(times),
            'traced_peak_bytes': peak, 'result_sha256': fingerprint}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--algorithm', choices=['md5', 'sha256'], default='sha256')
    parser.add_argument('--mode', choices=['streaming', 'retained'], default='streaming')
    parser.add_argument('--trials', type=int, default=100_000)
    parser.add_argument('--sizes', nargs='+', type=int, default=[1000, 10000, 100000])
    parser.add_argument('--payload-bytes', type=int, default=32)
    parser.add_argument('--seed', type=int, default=20261002)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, default=Path('benchmarks/latest.json'))
    args = parser.parse_args()
    if min(args.trials, args.payload_bytes, args.repeats, *args.sizes) < 1:
        parser.error('sizes, repeats and payload size must be positive')
    if args.worker:
        print(json.dumps(measure(args)))
        return
    rows = []
    for algorithm in ['md5', 'sha256']:
        for trials in args.sizes:
            expected = None
            for mode in ['streaming', 'retained']:
                command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--algorithm', algorithm,
                           '--mode', mode, '--trials', str(trials), '--payload-bytes', str(args.payload_bytes),
                           '--seed', str(args.seed), '--repeats', str(args.repeats)]
                row = json.loads(subprocess.check_output(command, text=True))
                if expected is not None and expected != row['result_sha256']:
                    raise AssertionError('Streaming and retained observations differ')
                expected = row['result_sha256']
                rows.append(row)
                print(algorithm, trials, mode, row['median_seconds'], row['traced_peak_bytes'], flush=True)
    root = Path(__file__).resolve().parents[1]
    report = {'schema_version': 1, 'platform': platform.platform(), 'python': platform.python_version(),
              'processor': platform.processor(), 'seed': args.seed, 'payload_bytes': args.payload_bytes,
              'repeats': args.repeats, 'timing_scope': 'untraced in-process experiment plus aggregate construction; excludes subprocess startup',
              'memory_scope': 'separate tracemalloc run: Python allocations only, excludes native OpenSSL allocations and total process RSS',
              'baseline': 'retained distances list then tuple, histogram and raw moments; not a rerun of the historical school experiment',
              'source_sha256': hashlib.sha256((root/'src/hash_avalanche/experiment.py').read_bytes()).hexdigest(),
              'records': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__': main()

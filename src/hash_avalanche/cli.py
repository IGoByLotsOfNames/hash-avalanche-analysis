from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiment import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the avalanche behaviour of hash functions")
    parser.add_argument("--algorithm", choices=("md5", "sha256"), default="sha256")
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--payload-bytes", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run_experiment(
        args.algorithm,
        trials=args.trials,
        payload_bytes=args.payload_bytes,
        seed=args.seed,
    )
    report = {
        "algorithm": result.algorithm,
        "trials": result.trials,
        "digest_bits": result.digest_bits,
        "normalized_mean": result.normalized_mean,
        "normalized_standard_deviation": result.normalized_standard_deviation,
        "distribution": result.distribution,
    }
    content = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()


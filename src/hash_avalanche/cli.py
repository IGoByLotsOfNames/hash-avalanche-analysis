from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiment import replay_report, run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the avalanche behaviour of hash functions")
    parser.add_argument("--algorithm", choices=("md5", "sha256"), default="sha256")
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--payload-bytes", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replay", type=Path, help="Replay and verify a schema-v2 report; uses its configuration")
    args = parser.parse_args()

    try:
        if args.replay:
            result = replay_report(json.loads(args.replay.read_text(encoding="utf-8")))
        else:
            result = run_experiment(args.algorithm, trials=args.trials,
                                    payload_bytes=args.payload_bytes, seed=args.seed)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    content = json.dumps(result.to_report(), indent=2, allow_nan=False)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
        except OSError as exc:
            parser.error(f"Cannot write report: {exc}")
    print(content)


if __name__ == "__main__":
    main()


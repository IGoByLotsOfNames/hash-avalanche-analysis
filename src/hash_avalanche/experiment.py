"""Seeded avalanche experiments with bounded memory and exact integer moments."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import platform
import random
import ssl

ALGORITHMS = ("md5", "sha256")
SCHEMA_VERSION = 2
EXPERIMENT_VERSION = "2.0.0"
SAMPLER_VERSION = "python-mt19937-getrandbits-le-randrange-v1"


def _integer(value: int, name: str, minimum: int | None = None) -> None:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError(f"{name} must be an integer" + (f" >= {minimum}" if minimum is not None else ""))


@dataclass(slots=True)
class DistanceAccumulator:
    """Mergeable histogram and exact raw moments; no trial list."""
    digest_bits: int
    counts: list[int] = field(init=False)
    count: int = field(init=False, default=0)
    total: int = field(init=False, default=0)
    total_squared: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        _integer(self.digest_bits, "digest_bits", 1)
        self.counts = [0] * (self.digest_bits + 1)

    def add(self, distance: int) -> None:
        _integer(distance, "distance", 0)
        if distance > self.digest_bits:
            raise ValueError("distance exceeds digest length")
        self.counts[distance] += 1
        self.count += 1
        self.total += distance
        self.total_squared += distance * distance

    def merge(self, other: DistanceAccumulator) -> None:
        if not isinstance(other, DistanceAccumulator) or other.digest_bits != self.digest_bits:
            raise ValueError("accumulators must have the same digest length")
        # Combining observations does not make repeated random streams independent.
        self.counts = [a + b for a, b in zip(self.counts, other.counts)]
        self.count += other.count
        self.total += other.total
        self.total_squared += other.total_squared


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    algorithm: str
    trials: int
    digest_bits: int
    payload_bytes: int
    seed: int
    histogram: tuple[int, ...]
    distance_sum: int
    distance_square_sum: int

    @property
    def normalized_mean(self) -> float:
        return self.distance_sum / (self.trials * self.digest_bits)

    @property
    def normalized_standard_deviation(self) -> float:
        numerator = self.trials * self.distance_square_sum - self.distance_sum ** 2
        return math.sqrt(numerator / self.trials ** 2) / self.digest_bits

    @property
    def normalized_standard_error(self) -> float | None:
        if self.trials < 2:
            return None
        numerator = self.trials * self.distance_square_sum - self.distance_sum ** 2
        return math.sqrt(numerator / (self.trials ** 2 * (self.trials - 1))) / self.digest_bits

    @property
    def mean_confidence_interval_95(self) -> tuple[float, float] | None:
        error = self.normalized_standard_error
        if error is None:
            return None
        margin = 1.959963984540054 * error
        return max(0.0, self.normalized_mean - margin), min(1.0, self.normalized_mean + margin)

    @property
    def distribution(self) -> dict[int, int]:
        return {distance: count for distance, count in enumerate(self.histogram) if count}

    def to_report(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "experiment_version": EXPERIMENT_VERSION,
            "sampler_version": SAMPLER_VERSION,
            "algorithm": self.algorithm,
            "trials": self.trials,
            "digest_bits": self.digest_bits,
            "payload_bytes": self.payload_bytes,
            "seed": self.seed,
            "bit_order": "LSB-first within each byte",
            "distance_sum": self.distance_sum,
            "distance_square_sum": self.distance_square_sum,
            "normalized_mean": self.normalized_mean,
            "normalized_standard_deviation": self.normalized_standard_deviation,
            "normalized_standard_error": self.normalized_standard_error,
            "mean_confidence_interval_95": self.mean_confidence_interval_95,
            "interval_method": "normal approximation using sample variance; Monte Carlo mean only",
            "distribution": self.distribution,
            "runtime": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                        "openssl": ssl.OPENSSL_VERSION},
        }


def flip_one_bit(payload: bytes, bit_index: int) -> bytes:
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("Payload must be nonempty bytes")
    _integer(bit_index, "bit_index", 0)
    if bit_index >= len(payload) * 8:
        raise IndexError("Bit index is outside the payload")
    output = bytearray(payload)
    byte_index, offset = divmod(bit_index, 8)
    output[byte_index] ^= 1 << offset
    return bytes(output)


def hamming_distance(left: bytes, right: bytes) -> int:
    if not isinstance(left, bytes) or not isinstance(right, bytes):
        raise ValueError("Digests must be bytes")
    if len(left) != len(right):
        raise ValueError("Digests must have equal length")
    return sum((a ^ b).bit_count() for a, b in zip(left, right))


def run_experiment(algorithm: str, *, trials: int, payload_bytes: int = 32,
                   seed: int = 42) -> ExperimentResult:
    if algorithm not in ALGORITHMS:
        raise ValueError("algorithm must be md5 or sha256 (fixed-length digests)")
    _integer(trials, "trials", 1)
    _integer(payload_bytes, "payload_bytes", 1)
    _integer(seed, "seed")
    rng = random.Random(seed)
    digest_bits = hashlib.new(algorithm, usedforsecurity=False).digest_size * 8
    stats = DistanceAccumulator(digest_bits)
    for _ in range(trials):
        payload = rng.getrandbits(payload_bytes * 8).to_bytes(payload_bytes, "little")
        modified = flip_one_bit(payload, rng.randrange(payload_bytes * 8))
        original_digest = hashlib.new(algorithm, payload, usedforsecurity=False).digest()
        modified_digest = hashlib.new(algorithm, modified, usedforsecurity=False).digest()
        stats.add(hamming_distance(original_digest, modified_digest))
    return ExperimentResult(algorithm, trials, digest_bits, payload_bytes, seed,
                            tuple(stats.counts), stats.total, stats.total_squared)


def replay_report(report: dict[str, object]) -> ExperimentResult:
    """Rerun a versioned report and verify exact integer observations."""
    if not isinstance(report, dict):
        raise ValueError("Replay report must be a JSON object")
    if (report.get("schema_version"), report.get("experiment_version"), report.get("sampler_version")) != (
        SCHEMA_VERSION, EXPERIMENT_VERSION, SAMPLER_VERSION
    ):
        raise ValueError("Unsupported report/experiment/sampler version")
    try:
        result = run_experiment(report["algorithm"], trials=report["trials"],
                                payload_bytes=report["payload_bytes"], seed=report["seed"])
        expected = {str(k): v for k, v in result.distribution.items()}
        observed = {str(k): v for k, v in report["distribution"].items()}
        if (observed != expected or report["digest_bits"] != result.digest_bits
                or report["distance_sum"] != result.distance_sum
                or report["distance_square_sum"] != result.distance_square_sum):
            raise ValueError("Replay did not match the recorded histogram/moments")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Malformed replay report") from exc
    return result

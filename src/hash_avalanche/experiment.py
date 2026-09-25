from __future__ import annotations

import hashlib
import random
import statistics
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    algorithm: str
    trials: int
    digest_bits: int
    distances: tuple[int, ...]

    @property
    def normalized_mean(self) -> float:
        return statistics.fmean(self.distances) / self.digest_bits

    @property
    def normalized_standard_deviation(self) -> float:
        return statistics.pstdev(self.distances) / self.digest_bits

    @property
    def distribution(self) -> dict[int, int]:
        return dict(sorted(Counter(self.distances).items()))


def flip_one_bit(payload: bytes, bit_index: int) -> bytes:
    if not payload:
        raise ValueError("Payload cannot be empty")
    if not 0 <= bit_index < len(payload) * 8:
        raise IndexError("Bit index is outside the payload")
    output = bytearray(payload)
    byte_index, offset = divmod(bit_index, 8)
    output[byte_index] ^= 1 << offset
    return bytes(output)


def hamming_distance(left: bytes, right: bytes) -> int:
    if len(left) != len(right):
        raise ValueError("Digests must have equal length")
    return sum((a ^ b).bit_count() for a, b in zip(left, right))


def run_experiment(
    algorithm: str,
    *,
    trials: int,
    payload_bytes: int = 32,
    seed: int = 42,
) -> ExperimentResult:
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Hash algorithm is unavailable: {algorithm}")
    if trials <= 0 or payload_bytes <= 0:
        raise ValueError("Trials and payload size must be positive")
    rng = random.Random(seed)
    distances: list[int] = []
    for _ in range(trials):
        payload = rng.randbytes(payload_bytes)
        modified = flip_one_bit(payload, rng.randrange(payload_bytes * 8))
        original_digest = hashlib.new(algorithm, payload).digest()
        modified_digest = hashlib.new(algorithm, modified).digest()
        distances.append(hamming_distance(original_digest, modified_digest))
    digest_bits = len(hashlib.new(algorithm).digest()) * 8
    return ExperimentResult(algorithm, trials, digest_bits, tuple(distances))


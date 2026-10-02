import collections
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import unittest

from hash_avalanche.experiment import (
    DistanceAccumulator, ExperimentResult, flip_one_bit, hamming_distance,
    replay_report, run_experiment,
)


class ExperimentTests(unittest.TestCase):
    def test_known_digests_and_bit_numbering(self):
        vectors = {
            'md5': '900150983cd24fb0d6963f7d28e17f72',
            'sha256': 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
        }
        for algorithm, expected in vectors.items():
            self.assertEqual(hashlib.new(algorithm, b'abc', usedforsecurity=False).hexdigest(), expected)
        self.assertEqual(flip_one_bit(b'\x00\x00', 0), b'\x01\x00')
        self.assertEqual(flip_one_bit(b'\x00\x00', 15), b'\x00\x80')

    def test_every_bit_flips_once_and_is_an_involution(self):
        rng = random.Random(8)
        for length in range(1, 18):
            payload = rng.randbytes(length)
            for bit in range(length * 8):
                changed = flip_one_bit(payload, bit)
                self.assertEqual(hamming_distance(payload, changed), 1)
                self.assertEqual(flip_one_bit(changed, bit), payload)

    def test_hamming_metric_properties(self):
        rng = random.Random(11)
        for _ in range(100):
            a, b, c = (rng.randbytes(32) for _ in range(3))
            self.assertEqual(hamming_distance(a, a), 0)
            self.assertEqual(hamming_distance(a, b), hamming_distance(b, a))
            self.assertLessEqual(hamming_distance(a, c), hamming_distance(a, b) + hamming_distance(b, c))
            self.assertEqual(hamming_distance(a, b), bin(int.from_bytes(a, 'big') ^ int.from_bytes(b, 'big')).count('1'))

    def test_streaming_matches_independent_retained_reference(self):
        for algorithm in ('md5', 'sha256'):
            for seed in (-7, 0, 42):
                rng = random.Random(seed)
                distances = []
                for _ in range(151):
                    payload = rng.randbytes(7)
                    bit = rng.randrange(56)
                    changed = bytearray(payload)
                    changed[bit // 8] ^= 2 ** (bit % 8)
                    a = hashlib.new(algorithm, payload, usedforsecurity=False).hexdigest()
                    b = hashlib.new(algorithm, changed, usedforsecurity=False).hexdigest()
                    distances.append(bin(int(a, 16) ^ int(b, 16)).count('1'))
                actual = run_experiment(algorithm, trials=151, payload_bytes=7, seed=seed)
                self.assertEqual(actual.distribution, dict(collections.Counter(distances)))
                self.assertEqual(actual.distance_sum, sum(distances))
                self.assertEqual(actual.distance_square_sum, sum(x*x for x in distances))
                self.assertAlmostEqual(actual.normalized_mean, statistics.mean(distances) / actual.digest_bits)
                self.assertAlmostEqual(actual.normalized_standard_deviation, statistics.pstdev(distances) / actual.digest_bits)
                self.assertAlmostEqual(actual.normalized_standard_error, statistics.stdev(distances) / math.sqrt(151) / actual.digest_bits)

    def test_merging_disjoint_batches_preserves_moments(self):
        values = [0, 8, 4, 4, 5, 0, 8, 3]
        whole = DistanceAccumulator(8)
        for value in values: whole.add(value)
        for split in range(len(values) + 1):
            first, second = DistanceAccumulator(8), DistanceAccumulator(8)
            for value in values[:split]: first.add(value)
            for value in values[split:]: second.add(value)
            first.merge(second)
            self.assertEqual(first, whole)
        with self.assertRaises(ValueError): whole.merge(DistanceAccumulator(9))

    def test_report_round_trip_and_tamper_detection(self):
        result = run_experiment('sha256', trials=1000, seed=20261002)
        report = json.loads(json.dumps(result.to_report(), allow_nan=False))
        self.assertEqual(replay_report(report), result)
        for key, value in [('seed', 5), ('distance_sum', 0), ('digest_bits', 1), ('schema_version', 1)]:
            tampered = copy.deepcopy(report)
            tampered[key] = value
            with self.assertRaises(ValueError): replay_report(tampered)
        for bad in ([], {}, {'schema_version': 2}):
            with self.assertRaises(ValueError): replay_report(bad)

    def test_single_trial_has_no_estimated_standard_error(self):
        result = run_experiment('md5', trials=1)
        self.assertEqual(result.normalized_standard_deviation, 0)
        self.assertIsNone(result.normalized_standard_error)
        self.assertIsNone(result.mean_confidence_interval_95)

    def test_degenerate_and_known_moments(self):
        result = ExperimentResult('test', 4, 8, 1, 0, (2, 0, 0, 0, 0, 0, 0, 0, 2), 16, 128)
        self.assertEqual(result.normalized_mean, .5)
        self.assertEqual(result.normalized_standard_deviation, .5)
        self.assertAlmostEqual(result.normalized_standard_error, math.sqrt(1/12))
        self.assertEqual(result.mean_confidence_interval_95, (0, 1))

    def test_validation(self):
        for algorithm in ('shake_128', 'SHA256', 'unknown', None):
            with self.assertRaises(ValueError): run_experiment(algorithm, trials=2)
        for parameter in ('trials', 'payload_bytes'):
            for value in (0, -1, True, 2.5, '2'):
                args = {'trials': 2, parameter: value}
                with self.assertRaises(ValueError): run_experiment('md5', **args)
        for seed in (True, 2.5, '2'):
            with self.assertRaises(ValueError): run_experiment('md5', trials=2, seed=seed)
        for value in (-1, 9, True, 1.5):
            with self.assertRaises(ValueError): DistanceAccumulator(8).add(value)
        with self.assertRaises(ValueError): flip_one_bit(b'', 0)
        with self.assertRaises(ValueError): flip_one_bit(b'a', -1)
        with self.assertRaises(IndexError): flip_one_bit(b'a', 8)
        with self.assertRaises(ValueError): hamming_distance(b'a', b'aa')

    def test_local_rng_does_not_modify_global_state(self):
        before = random.getstate()
        run_experiment('md5', trials=30)
        self.assertEqual(before, random.getstate())

    def test_cli_report_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            command = [sys.executable, '-m', 'hash_avalanche.cli']
            result = subprocess.run(command + ['--trials', '20', '--output', str(path)], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), json.loads(path.read_text()))
            replay = subprocess.run(command + ['--replay', str(path)], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), json.loads(replay.stdout))
            bad = subprocess.run(command + ['--trials', '0'], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertNotIn('Traceback', bad.stderr)
            bad_output = subprocess.run(command + ['--trials', '1', '--output', directory], capture_output=True, text=True)
            self.assertEqual(bad_output.returncode, 2)
            self.assertIn('Cannot write report', bad_output.stderr)
            self.assertNotIn('Traceback', bad_output.stderr)


if __name__ == '__main__':
    unittest.main()

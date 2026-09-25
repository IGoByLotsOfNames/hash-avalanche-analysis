import hashlib
import unittest

from hash_avalanche.experiment import flip_one_bit, hamming_distance, run_experiment


class ExperimentTests(unittest.TestCase):
    def test_flip_one_bit_changes_exactly_one_input_bit(self) -> None:
        original = b"abc"
        modified = flip_one_bit(original, 9)
        self.assertEqual(hamming_distance(original, modified), 1)

    def test_hamming_distance_matches_known_bytes(self) -> None:
        self.assertEqual(hamming_distance(bytes([0b0000]), bytes([0b1111])), 4)

    def test_seed_makes_experiment_reproducible(self) -> None:
        first = run_experiment("sha256", trials=25, seed=7)
        second = run_experiment("sha256", trials=25, seed=7)
        self.assertEqual(first.distances, second.distances)
        self.assertEqual(first.digest_bits, hashlib.sha256().digest_size * 8)


if __name__ == "__main__":
    unittest.main()


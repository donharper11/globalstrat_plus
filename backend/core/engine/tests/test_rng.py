"""Unit tests for the seeded-RNG utility — CC-3.5 §A.1."""
from django.test import SimpleTestCase

from core.engine.rng import get_rng


class TestGetRNG(SimpleTestCase):

    def test_same_triple_same_stream(self):
        """Same (class_id, round_number, operation_id) returns identical draws."""
        r1 = get_rng(42, 3, "event_trigger:7")
        r2 = get_rng(42, 3, "event_trigger:7")
        self.assertEqual(
            [r1.random() for _ in range(5)],
            [r2.random() for _ in range(5)],
        )

    def test_different_class_different_stream(self):
        r1 = get_rng(1, 3, "event_trigger:7")
        r2 = get_rng(2, 3, "event_trigger:7")
        self.assertNotEqual(r1.random(), r2.random())

    def test_different_round_different_stream(self):
        r1 = get_rng(42, 3, "event_trigger:7")
        r2 = get_rng(42, 4, "event_trigger:7")
        self.assertNotEqual(r1.random(), r2.random())

    def test_different_operation_different_stream(self):
        r1 = get_rng(42, 3, "event_trigger:7")
        r2 = get_rng(42, 3, "event_trigger:8")
        self.assertNotEqual(r1.random(), r2.random())

    def test_returns_random_Random_instance(self):
        import random
        r = get_rng(1, 1, "x")
        self.assertIsInstance(r, random.Random)

    def test_string_class_id_accepted(self):
        """class_id can be any stringifiable value."""
        r1 = get_rng("section-A", 1, "x")
        r2 = get_rng("section-A", 1, "x")
        self.assertEqual(r1.random(), r2.random())

    def test_draws_in_expected_range(self):
        r = get_rng(42, 3, "x")
        for _ in range(100):
            v = r.random()
            self.assertGreaterEqual(v, 0.0)
            self.assertLess(v, 1.0)

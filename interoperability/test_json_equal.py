"""Guard semantic comparison used by the Python parity client."""

import unittest

from a2a_schema_contract_reference.client import json_equal


class JsonEqualityTests(unittest.TestCase):
    def test_json_boolean_is_not_a_number(self):
        self.assertFalse(json_equal(True, 1))
        self.assertFalse(json_equal(0, False))
        self.assertFalse(json_equal({"items": [True]}, {"items": [1]}))
        self.assertTrue(json_equal({"items": [1]}, {"items": [1.0]}))


if __name__ == "__main__":
    unittest.main()

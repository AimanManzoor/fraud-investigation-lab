import unittest
from src.validation import numeric_issue


class ValidationTests(unittest.TestCase):
    def test_valid_amounts(self):
        for value in ["0", "181.0", "9839.64", " 12.50 ", "1e3"]:
            with self.subTest(value=value):
                self.assertEqual(numeric_issue(value), "valid")

    def test_invalid_amounts(self):
        cases = [
            (None, "missing"),
            ("", "missing"),
            ("abc", "not_numeric"),
            ("NaN", "non_finite"),
            ("Infinity", "non_finite"),
            ("-5", "negative"),
            ("1_000", "invalid_format"),
            ("1e999", "out_of_range"),
            ("1e-999", "out_of_range"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(numeric_issue(value), expected)

    def test_steps(self):
        cases = [
            ("1", "valid"),
            ("743", "valid"),
            ("0", "out_of_range"),
            ("-1", "negative"),
            ("1.5", "not_integer_literal"),
            ("1e3", "not_integer_literal"),
            ("9223372036854775808", "out_of_range"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    numeric_issue(value, integer=True), expected
                )


if __name__ == "__main__":
    unittest.main()

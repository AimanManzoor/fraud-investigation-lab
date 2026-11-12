import unittest
from src.money import MAX_INTEGER, to_minor_units


class MoneyTests(unittest.TestCase):
    def test_exact_conversion(self):
        cases = [
            ("9839.64", 983964),
            ("0.10", 10),
            ("0.20", 20),
            ("0.30", 30),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(to_minor_units(text), expected)

    def test_equivalent_text_formats(self):
        cases = [
            ("0", 0),
            ("181.0", 18100),
            (" 12.50 ", 1250),
            ("1e3", 100000),
            ("0.01000", 1),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(to_minor_units(text), expected)

    def test_excess_precision_is_rejected_without_rounding(self):
        for text in ["0.001", "12.345", "1e-3"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    to_minor_units(text)

    def test_invalid_and_nontext_values_are_rejected(self):
        values = [
            None, "", "abc", "-1", "NaN", "Infinity",
            "1_000", 0.1, 100, True,
        ]
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    to_minor_units(value)

    def test_integer_limits_and_large_exact_amounts(self):
        self.assertEqual(
            to_minor_units("92233720368547758.07"), MAX_INTEGER
        )
        self.assertEqual(
            to_minor_units("90071992547409.93"), 9007199254740993
        )
        for text in ["92233720368547758.08", "1e20"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    to_minor_units(text)


if __name__ == "__main__":
    unittest.main()

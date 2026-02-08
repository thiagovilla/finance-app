import unittest
from datetime import date

from itau_pdf.utils import normalize_text, parse_brl_amount, dmy_to_mdy, parse_dm_date


class TestUtils(unittest.TestCase):

    def test_normalize_text(self):
        # Test accent removal and lowercasing
        self.assertEqual(normalize_text("Olá Mundo"), "olamundo")
        # Test whitespace stripping (all spaces should be removed per regex)
        self.assertEqual(normalize_text("  Lançamentos: Compras  "), "lancamentos:compras")
        # Test complex unicode
        self.assertEqual(normalize_text("Açúcar e Café"), "acucarecafe")

    def test_parse_brl_amount(self):
        # Standard BRL format
        self.assertEqual(parse_brl_amount("1.234,56"), 1234.56)
        # Without thousands separator
        self.assertEqual(parse_brl_amount("56,78"), 56.78)
        # With whitespace and space between sign and value
        self.assertEqual(parse_brl_amount("  1.000,00  "), 1000.0)
        self.assertEqual(parse_brl_amount("- 150,00"), -150.0)
        self.assertEqual(parse_brl_amount("-  150,00"), -150.0)

    def test_dmy_to_mdy(self):
        # Valid date conversion
        self.assertEqual(dmy_to_mdy("15/02/25"), "02/15/25")
        self.assertEqual(dmy_to_mdy("01/10/24"), "10/01/24")
        # Empty string
        self.assertEqual(dmy_to_mdy(""), "")
        # Invalid format should return original string
        self.assertEqual(dmy_to_mdy("2025-02-15"), "2025-02-15")
        self.assertEqual(dmy_to_mdy("not-a-date"), "not-a-date")

    def test_parse_dm_date(self):
        self.assertEqual(parse_dm_date("15/02"), date(1900, 2, 15))
        # Invalid formats
        self.assertEqual(parse_dm_date(""), None)
        self.assertEqual(parse_dm_date("15/02/2024"), None)
        self.assertEqual(parse_dm_date("not-a-date"), None)

if __name__ == "__main__":
    unittest.main()
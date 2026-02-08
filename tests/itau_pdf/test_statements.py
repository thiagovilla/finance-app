import unittest
from datetime import date
from itau_pdf.layout import Line
from itau_pdf.statements import parse_lines, Statement

payment_date = date(2025, 2, 15)


class TestStatements(unittest.TestCase):
    def test_parse_lines_basic(self):
        lines = [
            Line(text="23/01 AMAZON*MARKETPLACE 02/08 -170,00"),
            Line(text="DIVERSOS . CURITIBA"),
            Line(text="15/02 IFOOD 42,50"),
            Line(text="ALIMENTACAO"),
        ]
        results = list(parse_lines(iter(lines), payment_date))
        self.assertEqual(len(results), 2)

        # Check first statement (with installments and negative sign flipped to positive)
        self.assertEqual(results[0].date, date(2025, 1, 23))
        self.assertEqual(results[0].description, "AMAZON*MARKETPLACE 02/08")
        self.assertEqual(results[0].amount, 170.00)
        self.assertEqual(results[0].category, "DIVERSOS")
        self.assertEqual(results[0].location, "CURITIBA")
        self.assertEqual(results[0].id, "2025-Feb-001")

        # Check second statement (positive amount flipped to negative)
        self.assertEqual(results[1].date, date(2025, 2, 15))
        self.assertEqual(results[1].description, "IFOOD")
        self.assertEqual(results[1].amount, -42.50)
        self.assertEqual(results[1].category, "ALIMENTACAO")
        self.assertEqual(results[1].location, "")
        self.assertEqual(results[1].id, "2025-Feb-002")

    def test_parse_lines_trailing_statement(self):
        # Tests that a statement is yielded even if it doesn't have a second "category" line
        lines = [Line(text="10/03 UNFINISHED TXN 10,00")]
        results = list(parse_lines(iter(lines), payment_date))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].description, "UNFINISHED TXN")
        self.assertEqual(results[0].category, "")

    def test_parse_lines_skips_empty(self):
        lines = [
            Line(text="   "),
            Line(text="10/03 VALID 10,00"),
            Line(text=""),
            Line(text="CAT"),
        ]
        results = list(parse_lines(iter(lines), payment_date))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].description, "VALID")

    def test_parse_lines_december_january_transition(self):
        """Tests that dates are mapped to previous year when in January"""
        payment_date = date(2025, 1, 15)
        lines = [
            Line(text="20/12 PREVIOUS YEAR 10,00"),
            Line(text="05/01 CURRENT YEAR 10,00"),
        ]
        results = list(parse_lines(iter(lines), payment_date))

        self.assertEqual(results[0].date, date(2024, 12, 20))
        self.assertEqual(results[1].date, date(2025, 1, 5))

import unittest
from datetime import date
from itau_pdf.layout import Line
from itau_pdf.statements import parse_lines, flip_sign, Statement, add_year, add_id


class TestStatements(unittest.TestCase):
    def test_parse_lines_basic(self):
        lines = [
            Line(text="23/01 AMAZON*MARKETPLACE 02/08 -170,00"),
            Line(text="DIVERSOS . CURITIBA"),
            Line(text="15/02 IFOOD 42,50"),
            Line(text="ALIMENTACAO"),
        ]
        results = list(parse_lines(iter(lines)))
        self.assertEqual(len(results), 2)

        # Check first statement (with installments and negative sign)
        self.assertEqual(results[0].date, "23/01")
        self.assertEqual(results[0].description, "AMAZON*MARKETPLACE 02/08")
        self.assertEqual(results[0].amount, -170.00)
        self.assertEqual(results[0].category, "DIVERSOS")
        self.assertEqual(results[0].location, "CURITIBA")

        # Check second statement (simple amount and no location separator)
        self.assertEqual(results[1].date, "15/02")
        self.assertEqual(results[1].description, "IFOOD")
        self.assertEqual(results[1].amount, 42.50)
        self.assertEqual(results[1].category, "ALIMENTACAO")
        self.assertEqual(results[1].location, "")

    def test_parse_lines_trailing_statement(self):
        # Tests that a statement is yielded even if it doesn't have a second "category" line
        lines = [
            Line(text="10/03 UNFINISHED TXN 10,00"),
        ]
        results = list(parse_lines(iter(lines)))
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
        results = list(parse_lines(iter(lines)))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].description, "VALID")

    def test_flip_sign(self):
        """Tests sign is flipped on each statement"""
        statements = [
            Statement(amount=100.0),
            Statement(amount=-50.0),
        ]
        flipped = list(flip_sign(iter(statements)))
        self.assertEqual(flipped[0].amount, -100.0)
        self.assertEqual(flipped[1].amount, 50.0)

    def test_add_year_basic(self):
        """Tests that add_year converts date strings to datetime dates"""
        issue_date = date(2024, 3, 15)
        statements = [
            Statement(date="10/01", amount=100.0),
            Statement(date="15/02", amount=50.0),
            Statement(date="20/03", amount=25.0),
        ]
        results = list(add_year(iter(statements), issue_date))

        self.assertEqual(results[0].date, date(2024, 1, 10))
        self.assertEqual(results[1].date, date(2024, 2, 15))
        self.assertEqual(results[2].date, date(2024, 3, 20))

    def test_add_year_december_january_transition(self):
        """Tests that add_year handles year transition correctly"""
        # Issue date in January should map December dates to previous year
        issue_date = date(2024, 1, 15)
        statements = [
            Statement(date="20/12", amount=100.0),
            Statement(date="25/12", amount=50.0),
            Statement(date="05/01", amount=25.0),
            Statement(date="10/01", amount=10.0),
        ]
        results = list(add_year(iter(statements), issue_date))

        # December dates should be from previous year
        self.assertEqual(results[0].date, date(2023, 12, 20))
        self.assertEqual(results[1].date, date(2023, 12, 25))
        # January dates should be from current year
        self.assertEqual(results[2].date, date(2024, 1, 5))
        self.assertEqual(results[3].date, date(2024, 1, 10))

    def test_add_id(self):
        """Tests that add_id generates IDs in YYYY-MMM-<index> format"""
        payment_date = date(2024, 3, 15)
        statements = [
            Statement(amount=100.0),
            Statement(amount=50.0),
            Statement(amount=25.0),
        ]
        results = list(add_id(iter(statements), payment_date))

        self.assertEqual(results[0].id, "2024-Mar-1")
        self.assertEqual(results[1].id, "2024-Mar-2")
        self.assertEqual(results[2].id, "2024-Mar-3")

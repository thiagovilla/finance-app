import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from finance_cli.itau import get_pdf_text
from itau_pdf.metadata import extract_last4, extract_total, extract_payment_date, extract_issue_date


class TestItauMetadata(unittest.TestCase):
    @patch("fitz.open")
    def test_get_pdf_text(self, mock_open):
        # Setup mock PDF structure
        mock_pdf = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Page 2 content"

        mock_pdf.__iter__.return_value = [mock_page1, mock_page2]
        mock_pdf.__enter__.return_value = mock_pdf
        mock_open.return_value = mock_pdf

        result = get_pdf_text("dummy.pdf")

        self.assertEqual(result, "Page 1 content\nPage 2 content")
        mock_open.assert_called_once_with("dummy.pdf")

    def test_extract_last4(self):
        # Test modern layout pattern
        self.assertEqual(extract_last4("Cartão final XXXX.7180"), "7180")
        self.assertEqual(extract_last4("No do cartão: xxxx.1234"), "1234")

        # Test no match
        self.assertIsNone(extract_last4("No card number here"))

    def test_extract_total(self):
        # Test various patterns found in Itaú PDFs
        self.assertEqual(extract_total("Total desta fatura\n R$ 1.234,56"), 1234.56)
        self.assertEqual(extract_total("O total da sua fatura é:\nR$ 500,00"), 500.0)
        self.assertEqual(extract_total("Total da fatura\n 89,90"), 89.9)

        # Test negative/ignoring anterior
        text_with_anterior = "Total da fatura anterior R$ 100,00\nTotal da fatura\n R$ 250,00"
        self.assertEqual(extract_total(text_with_anterior), 250.0)

        self.assertIsNone(extract_total("No total mentioned"))

    def test_extract_payment_date(self):
        # Test standard match
        text = "Vencimento 20/10/2025"
        self.assertEqual(extract_payment_date(text), datetime(2025, 10, 20))

        # Test match with extra characters (the \D{0,20} part)
        text_extra = "Vencimento:  -------  15/02/2026"
        self.assertEqual(extract_payment_date(text_extra), datetime(2026, 2, 15))

        # Test fallback to normalized text search
        text_norm = "DATA DE VENCIMENTO\n05/12/2025"
        self.assertEqual(extract_payment_date(text_norm), datetime(2025, 12, 5))

        # Test invalid date/no match
        self.assertIsNone(extract_payment_date("Vencimento 99/99/9999"))
        self.assertIsNone(extract_payment_date("No date here"))

    def test_extract_issue_date(self):
        # Test standard match
        text = "Emissão 15/09/2025"
        self.assertEqual(extract_issue_date(text), datetime(2025, 9, 15))

        # Test invalid date/no match
        self.assertIsNone(extract_issue_date("Emissão 99/99/9999"))
        self.assertIsNone(extract_issue_date("No date here"))


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch, MagicMock
from category.categorize import categorize, find_exact_match
from category.models import Suggestion, Category


class TestMain(unittest.TestCase):

    @patch("category.main.connect_db")
    @patch("category.main.find_exact_match")
    @patch("category.main.canonicalize_description")
    def test_categorize_exact_match(self, mock_canonicalize, mock_find_exact, mock_db):
        # Setup
        mock_canonicalize.return_value = "amazon"
        mock_find_exact.return_value = Category(name="Shopping")

        # Execute
        result = categorize("AMAZON.COM")

        # Assert
        self.assertEqual(result.name, "Shopping")
        mock_find_exact.assert_called_once()

    @patch("category.main.connect_db")
    @patch("category.main.fuzzy_search")
    @patch("category.main.find_exact_match")
    def test_categorize_fuzzy_match_high_confidence(self, mock_find_exact, mock_fuzzy, mock_db):
        # Setup
        mock_find_exact.return_value = None
        mock_fuzzy.return_value = [Suggestion(category=Category(name="Food"), confidence=0.9)]

        # Execute
        result = categorize("IFOOD", threshold=0.8)

        # Assert
        self.assertEqual(result.name, "Food")
        mock_fuzzy.assert_called_once()

    @patch("category.main.connect_db")
    @patch("category.main.ask_single")
    @patch("category.main.fuzzy_search")
    @patch("category.main.find_exact_match")
    def test_categorize_ai_fallback(self, mock_find_exact, mock_fuzzy, mock_ai, mock_db):
        # Setup
        mock_find_exact.return_value = None
        mock_fuzzy.return_value = []  # No fuzzy results
        mock_ai.return_value = [Suggestion(category=Category(name="Transport"), confidence=0.95)]

        # Execute
        result = categorize("UBER TRIP", threshold=0.9)

        # Assert
        self.assertEqual(result.name, "Transport")
        mock_ai.assert_called_once()

    def test_find_exact_match_found(self):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ["Health"]

        result = find_exact_match(mock_conn, "pharmacy")

        self.assertEqual(result, "Health")
        mock_conn.execute.assert_called_with(
            "SELECT category FROM categorizations WHERE canonical_description = ?",
            ("pharmacy",)
        )

    def test_find_exact_match_not_found(self):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None

        result = find_exact_match(mock_conn, "unknown")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

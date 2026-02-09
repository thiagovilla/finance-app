import unittest
import csv
from datetime import date
from pathlib import Path
import tempfile
import shutil
from src.core.common import Statement, write_statements_csv

class TestCommon(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for file operations
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_csv = self.test_dir / "test_statements.csv"

    def tearDown(self):
        # Clean up the directory after tests
        shutil.rmtree(self.test_dir)

    def test_statement_to_dict(self):
        """Test that Statement correctly converts to a dictionary with formatted strings."""
        stmt = Statement(
            id="2024-01-001",
            transaction_date=date(2024, 1, 15),
            description="Test Purchase",
            amount=150.5,
            payment_date=date(2024, 2, 1),
            category="Shopping",
            account="Checking"
        )

        data = stmt.to_dict()

        self.assertEqual(data["id"], "2024-01-001")
        self.assertEqual(data["transaction_date"], "2024-01-15")
        self.assertEqual(data["payment_date"], "2024-02-01")
        self.assertEqual(data["amount"], "150.50")
        self.assertEqual(data["description"], "Test Purchase")

    def test_statement_to_dict_no_payment_date(self):
        """Test to_dict when payment_date is None."""
        stmt = Statement(
            id="2024-01-002",
            transaction_date=date(2024, 1, 15),
            description="No Payment Date",
            amount=10.0
        )
        data = stmt.to_dict()
        self.assertEqual(data["payment_date"], "")

    def test_write_statements_csv_new_file(self):
        """Test writing statements to a new CSV file."""
        statements = [
            Statement("id1", date(2024, 1, 1), "Item 1", 10.0),
            Statement("id2", date(2024, 1, 2), "Item 2", 20.0),
        ]

        count = write_statements_csv(statements, self.test_csv)

        self.assertEqual(count, 2)
        self.assertTrue(self.test_csv.exists())

        with open(self.test_csv, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 2)
            self.assertEqual(reader[0]["id"], "id1")
            self.assertEqual(reader[1]["amount"], "20.00")

    def test_write_statements_csv_idempotency_by_default(self):
        """Test that writing to an existing file is idempotent by default."""
        initial = [Statement("id1", date(2024, 1, 1), "Item 1", 10.0)]
        write_statements_csv(initial, self.test_csv)

        # Try to write the same ID again without append/force
        new_batch = [
            Statement("id1", date(2024, 1, 1), "Item 1", 10.0), # Duplicate
            Statement("id2", date(2024, 1, 2), "Item 2", 20.0), # New
        ]

        count = write_statements_csv(new_batch, self.test_csv)

        self.assertEqual(count, 1, "Should only write 1 new statement even without explicit append=True")

        with open(self.test_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)

    def test_write_statements_csv_force_overwrite(self):
        """Test that force=True completely overwrites the existing file."""
        initial = [
            Statement("id1", date(2024, 1, 1), "Item 1", 10.0),
            Statement("id2", date(2024, 1, 2), "Item 2", 20.0),
        ]
        write_statements_csv(initial, self.test_csv)

        # Force overwrite with completely new statements
        new_statements = [
            Statement("id3", date(2024, 1, 3), "Item 3", 30.0),
            Statement("id4", date(2024, 1, 4), "Item 4", 40.0),
        ]

        count = write_statements_csv(new_statements, self.test_csv, force=True)

        self.assertEqual(count, 2, "Both new statements should have been written")

        with open(self.test_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2, "File should only contain the new statements")
            ids = [row["id"] for row in rows]
            self.assertIn("id3", ids)
            self.assertIn("id4", ids)
            self.assertNotIn("id1", ids, "Old statements should be gone")
            self.assertNotIn("id2", ids, "Old statements should be gone")


if __name__ == "__main__":
    unittest.main()
import unittest
from unittest.mock import MagicMock, patch
from itau_pdf.layout import Page, Column, Block, _has_marker, _split_columns, _iter_lines
from itau_pdf.layout_lines import Line


class TestItauBlocks(unittest.TestCase):
    def test_check_marker(self):
        # Test start marker
        start_block = Block(page=1, column=Column.left, x0=10, y0=10, text="Lançamentos: Compras e Saques")
        self.assertTrue(_has_marker(start_block, "start"))

        # Test stop marker
        stop_block = Block(page=1, column=Column.right, x0=10, y0=10, text="Compras Parceladas")
        self.assertTrue(_has_marker(stop_block, "stop"))

        # Test non-marker
        normal_block = Block(page=1, column=Column.left, x0=10, y0=10, text="Padaria do Zé")
        self.assertFalse(_has_marker(normal_block, "start"))
        self.assertFalse(_has_marker(normal_block, "stop"))

    def test_iter_blocks(self):
        # Mocking Page and its columns
        mock_page = MagicMock(spec=Page)
        mock_page.index = 5

        left_line = Line(y0=100, x0=10, y1=110, x1=20, text="Hello")
        right_line = Line(y0=100, x0=300, y1=110, x1=315, text="World")

        with patch('itau_pdf.layout_blocks._split_into_columns') as mock_split:
            mock_split.return_value = {
                Column.left: [left_line],
                Column.right: [right_line]
            }

            blocks = list(_iter_lines(mock_page))

            self.assertEqual(len(blocks), 2)
            # Order should be Left then Right
            self.assertEqual(blocks[0].text, "Hello")
            self.assertEqual(blocks[0].column, Column.left)
            self.assertEqual(blocks[1].text, "World")
            self.assertEqual(blocks[1].column, Column.right)
            self.assertEqual(blocks[0].page, 5)

    def test_split_into_columns(self):
        # Mock fitz.Page object
        mock_page_obj = MagicMock()
        # Mock get_text("words") returns: x0, y0, x1, y1, text, ...
        mock_page_obj.get_text.return_value = [
            (10, 100, 50, 110, "Left1"),
            (300, 100, 350, 110, "Right1"),
            (15, 120, 55, 130, "Left2"),
        ]

        # Page with split at 200
        page = Page(index=0, pdf=mock_page_obj, x_split=200.0)

        with patch('itau_pdf.layout_blocks.group_words_into_lines') as mock_group:
            # Mock group_words_into_lines to just return what it's given as "Lines"
            mock_group.side_effect = lambda words: [Line(y0=w.y0, x0=w.x0, y1=w.y1, x1=w.x1, text=w.text) for w in words]

            columns = _split_columns(page)

            self.assertEqual(len(columns[Column.left]), 2)
            self.assertEqual(len(columns[Column.right]), 1)
            self.assertEqual(columns[Column.left][0].text, "Left1")
            self.assertEqual(columns[Column.right][0].text, "Right1")

    def test_split_into_columns_empty(self):
        mock_page_obj = MagicMock()
        mock_page_obj.get_text.return_value = []
        page = Page(index=0, pdf=mock_page_obj, x_split=200.0)

        self.assertIsNone(_split_columns(page))


if __name__ == "__main__":
    unittest.main()

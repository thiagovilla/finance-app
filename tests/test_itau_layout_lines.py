import unittest
from itau_pdf.layout_lines import Word, Line, group_words_into_lines, _calc_y_tol


class TestItauLines(unittest.TestCase):
    def test_calc_y_tol(self):
        # Words with height of 10
        words = [
            Word(x0=0, y0=0, x1=10, y1=10, text="a"),
            Word(x0=0, y0=20, x1=10, y1=30, text="b"),
        ]
        # median height = 10. 10 * 0.3 = 3.0.
        self.assertEqual(_calc_y_tol(words), 3.0)

        # Words with very small height
        small_words = [Word(x0=0, y0=0, x1=1, y1=1, text="tiny")]
        # median height = 1. 1 * 0.3 = 0.3. Max(2.0, 0.3) = 2.0
        self.assertEqual(_calc_y_tol(small_words), 2.0)

    def test_group_words_into_lines_simple(self):
        words = [
            Word(x0=10, y0=10, x1=50, y1=20, text="Hello"),
            Word(x0=60, y0=10, x1=100, y1=20, text="World"),
            Word(x0=10, y0=50, x1=50, y1=60, text="Second"),
            Word(x0=60, y0=51, x1=100, y1=61, text="Line"),
        ]

        lines = group_words_into_lines(words)

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].text, "Hello World")
        self.assertEqual(lines[1].text, "Second Line")
        # Check coordinates of the first line
        self.assertEqual(lines[0].y0, 10)
        self.assertEqual(lines[0].x0, 10)

    def test_group_words_into_lines_sorting(self):
        # Words out of order
        words = [
            Word(x0=60, y0=10, x1=100, y1=20, text="World"),
            Word(x0=10, y0=50, x1=50, y1=60, text="Second"),
            Word(x0=10, y0=10, x1=50, y1=20, text="Hello"),
        ]

        lines = group_words_into_lines(words)

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].text, "Hello World")
        self.assertEqual(lines[1].text, "Second")

    def test_group_words_into_lines_empty(self):
        self.assertEqual(group_words_into_lines([]), [])

    def test_group_words_into_lines_whitespace_only(self):
        words = [Word(x0=10, y0=10, x1=20, y1=20, text="   ")]
        self.assertEqual(group_words_into_lines(words), [])


if __name__ == "__main__":
    unittest.main()
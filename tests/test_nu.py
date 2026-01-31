from pathlib import Path

import pandas as pd

from finance_cli.nu import convert_date_format


def test_convert_date_format(tmp_path: Path) -> None:
    csv_path = tmp_path / "nu.csv"
    df = pd.DataFrame(
        {
            "date": ["2025-01-02", "2025-02-03"],
            "desc": ["Coffee", "Groceries"],
            "amount": [10.0, -20.5],
        }
    )
    df.to_csv(csv_path, index=False)

    convert_date_format(csv_path)

    result = pd.read_csv(csv_path)
    assert result.iloc[0, 0] == "02/01/2025"
    assert result.iloc[1, 0] == "03/02/2025"
    assert result.iloc[0, 2] == -10.0
    assert result.iloc[1, 2] == 20.5


def test_convert_date_format_output_path(tmp_path: Path) -> None:
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"

    pd.DataFrame({"date": ["2025-01-02"], "amount": [5.0]}).to_csv(
        input_path, index=False
    )

    convert_date_format(input_path, output_path)

    assert output_path.exists()

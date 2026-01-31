from __future__ import annotations

from pathlib import Path

import pandas as pd


def convert_date_format(input_csv: Path, output_csv: Path | None = None) -> Path:
    """Convert the first column to DD/MM/YYYY and flip the third column sign.

    Returns the output path.
    """
    output_path = output_csv or input_csv

    df = pd.read_csv(input_csv)
    df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0]).dt.strftime("%d/%m/%Y")

    if len(df.columns) > 2:
        df.iloc[:, 2] *= -1

    df.to_csv(output_path, index=False)
    return output_path

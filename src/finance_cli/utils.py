import glob
from pathlib import Path


def resolve_itau_inputs(input_path: str) -> list[Path]:
    if any(char in input_path for char in ["*", "?", "["]):
        matches = [Path(path) for path in glob.glob(input_path)]
    else:
        path = Path(input_path)
        if path.is_dir():
            matches = sorted(path.glob("*.pdf"))
        else:
            matches = [path]

    pdfs = [path for path in matches if path.is_file() and path.suffix.lower() == ".pdf"]
    if not pdfs:
        raise ValueError(f"No PDF files found for input: {input_path}")
    return pdfs

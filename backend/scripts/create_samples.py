import csv
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    csv_paths = [Path(item) for item in sys.argv[1:]] or sorted(
        (root / "samples").glob("sample_*.csv")
    )
    for csv_path in csv_paths:
        xlsx_path = csv_path.with_suffix(".xlsx")
        with csv_path.open(encoding="utf-8", newline="") as source:
            rows = list(csv.reader(source))
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Data OPD"
        sheet.append([])
        for row in rows:
            sheet.append(row)
        if csv_path.name == "sample_date_quality.csv":
            sheet["A9"] = datetime(2025, 1, 29)
        elif csv_path.name == "sample_numeric_quality.csv":
            for row in sheet.iter_rows(min_row=3, max_row=11):
                for cell in row:
                    cell.value = int(cell.value)
            sheet["H12"] = True
        workbook.save(xlsx_path)
        print(f"Created {xlsx_path}")


if __name__ == "__main__":
    main()

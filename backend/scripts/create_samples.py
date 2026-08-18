import csv
from pathlib import Path

from openpyxl import Workbook


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    for csv_path in sorted((root / "samples").glob("sample_*.csv")):
        xlsx_path = csv_path.with_suffix(".xlsx")
        with csv_path.open(encoding="utf-8", newline="") as source:
            rows = list(csv.reader(source))
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Data OPD"
        sheet.append([])
        for row in rows:
            sheet.append(row)
        workbook.save(xlsx_path)
        print(f"Created {xlsx_path}")


if __name__ == "__main__":
    main()

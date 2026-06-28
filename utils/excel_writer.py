from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font


LINK_COLUMNS = {"Job Link"}


class ExcelWriter:
    @staticmethod
    def write_rows(file_path, rows, sheet_name="Sheet1"):
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            ExcelWriter._write_workbook(path, rows, sheet_name)
            return path
        except PermissionError:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fallback_path = path.with_name(f"{path.stem}_{timestamp}{path.suffix}")
            ExcelWriter._write_workbook(fallback_path, rows, sheet_name)
            return fallback_path

    @staticmethod
    def _write_workbook(path, rows, sheet_name):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = sheet_name

        for row in rows:
            worksheet.append(row)

        ExcelWriter._apply_hyperlinks(worksheet)
        workbook.save(path)

    @staticmethod
    def _apply_hyperlinks(worksheet):
        headers = [cell.value for cell in worksheet[1]]
        link_column_indexes = [
            index for index, header in enumerate(headers, start=1) if header in LINK_COLUMNS
        ]

        for column_index in link_column_indexes:
            for row in worksheet.iter_rows(
                min_row=2,
                min_col=column_index,
                max_col=column_index,
            ):
                cell = row[0]
                if not cell.value:
                    continue
                cell.hyperlink = str(cell.value)
                cell.style = "Hyperlink"
                cell.font = Font(color="0563C1", underline="single")

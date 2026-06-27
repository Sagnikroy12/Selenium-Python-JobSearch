import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


class ExcelWriter:
    @staticmethod
    def write_rows(file_path, rows, sheet_name="Sheet1"):
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        package_parts = ExcelWriter._build_package_parts(rows, sheet_name)

        try:
            ExcelWriter._write_package(path, package_parts)
            return path
        except PermissionError:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            fallback_path = path.with_name(f"{path.stem}_{timestamp}{path.suffix}")
            ExcelWriter._write_package(fallback_path, package_parts)
            return fallback_path

    @staticmethod
    def _build_package_parts(rows, sheet_name):
        sheet_rows = []
        for row_idx, row in enumerate(rows, start=1):
            cells = "".join(
                ExcelWriter._cell_xml(row_idx, col_idx, value)
                for col_idx, value in enumerate(row, start=1)
            )
            sheet_rows.append(f'<row r="{row_idx}">{cells}</row>')

        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheetData>{"".join(sheet_rows)}</sheetData>'
            '</worksheet>'
        )

        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>'
        )

        workbook_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        )

        root_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '</Relationships>'
        )

        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        )

        return {
            "[Content_Types].xml": content_types_xml,
            "_rels/.rels": root_rels_xml,
            "xl/workbook.xml": workbook_xml,
            "xl/_rels/workbook.xml.rels": workbook_rels_xml,
            "xl/worksheets/sheet1.xml": sheet_xml,
        }

    @staticmethod
    def _write_package(path, package_parts):
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as xlsx:
            for package_path, content in package_parts.items():
                xlsx.writestr(package_path, content)

    @staticmethod
    def _cell_xml(row_idx, col_idx, value):
        ref = f"{ExcelWriter._column_letter(col_idx)}{row_idx}"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c r="{ref}"><v>{value}</v></c>'

        value_text = escape("" if value is None else str(value))
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{value_text}</t></is></c>'

    @staticmethod
    def _column_letter(index):
        letters = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters

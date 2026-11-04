import base64
import csv
import io
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook

MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def history_content(filename: str, content: bytes) -> dict[str, object]:
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Размер файла должен быть от 1 байта до 8 МБ")
    extension = Path(filename).suffix.lower()
    if extension in {".png", ".jpg", ".jpeg", ".webp"}:
        valid = (
            content.startswith(b"\x89PNG\r\n\x1a\n")
            if extension == ".png"
            else content.startswith(b"\xff\xd8")
            if extension in {".jpg", ".jpeg"}
            else content.startswith(b"RIFF") and content[8:12] == b"WEBP"
        )
        if not valid:
            raise ValueError("Файл не соответствует формату изображения")
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }[extension]
        return {
            "type": "input_image",
            "image_url": "data:" + mime + ";base64," + base64.b64encode(content).decode(),
        }
    if extension == ".xlsx":
        with ZipFile(io.BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 30 * 1024 * 1024:
                raise ValueError("Слишком большой распакованный файл")
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        lines: list[str] = []
        try:
            for sheet in workbook.worksheets[:10]:
                lines.append("Лист: " + sheet.title)
                for row in sheet.iter_rows(max_row=1000, max_col=50, values_only=True):
                    values = [str(cell) if cell is not None else "" for cell in row]
                    if any(values):
                        lines.append(" | ".join(values))
        finally:
            workbook.close()
        text = "\n".join(lines)
    elif extension in {".csv", ".txt"}:
        text = content.decode("utf-8-sig")
        if extension == ".csv":
            text = "\n".join(" | ".join(row) for row in list(csv.reader(io.StringIO(text)))[:1000])
    else:
        raise ValueError("Поддерживаются XLSX, CSV, TXT, PNG, JPG и WEBP")
    if len(text) > 120000:
        raise ValueError("Слишком много данных. Оставьте два месяца истории")
    return {"type": "input_text", "text": "Файл " + Path(filename).name + ":\n" + text}

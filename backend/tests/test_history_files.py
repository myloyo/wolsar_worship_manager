import io

import pytest
from openpyxl import Workbook
from worship_bot.infrastructure.history_files import MAX_UPLOAD_BYTES, history_content


def test_xlsx_history_preserves_dates_and_names() -> None:
    # Arrange
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["Дата", "Вокал"])
    sheet.append(["2026-10-04", "Анна"])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()

    # Act
    content = history_content("history.xlsx", stream.getvalue())

    # Assert
    assert content["type"] == "input_text"
    assert "Анна" in str(content["text"])
    assert "2026-10-04" in str(content["text"])


def test_oversized_upload_is_rejected() -> None:
    # Arrange
    content = b"a" * (MAX_UPLOAD_BYTES + 1)

    # Act / Assert
    with pytest.raises(ValueError, match="8 МБ"):
        history_content("history.csv", content)


def test_fake_image_is_rejected() -> None:
    # Act / Assert
    with pytest.raises(ValueError, match="формату"):
        history_content("history.png", b"not an image")


def test_csv_history_decodes_utf8_bom() -> None:
    # Arrange
    content = "Дата,Имя\n2026-10-04,Анна".encode("utf-8-sig")

    # Act
    result = history_content("history.csv", content)

    # Assert
    assert "Анна" in str(result["text"])

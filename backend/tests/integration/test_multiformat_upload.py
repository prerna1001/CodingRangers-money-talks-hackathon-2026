from __future__ import annotations

from fastapi.testclient import TestClient

from api.routes.upload import _UPLOADED_FILES
from main import app


def test_csv_upload_remains_analyzable() -> None:
    _UPLOADED_FILES.clear()
    client = TestClient(app)
    response = client.post(
        "/api/upload",
        files={"file": ("transactions.csv", b"date,account,account_type,amount\n2026-08-01,Sales,revenue,1200\n", "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_type"] == "transaction_csv"
    assert body["review_status"] == "ready"


def test_extracted_xlsx_is_normalized_without_a_second_upload_step() -> None:
    from io import BytesIO
    from openpyxl import Workbook

    _UPLOADED_FILES.clear()
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["date", "account", "account_type", "amount"])
    worksheet.append(["2026-08-01", "Sales", "revenue", 1200])
    buffer = BytesIO()
    workbook.save(buffer)
    client = TestClient(app)

    uploaded = client.post(
        "/api/upload",
        files={"file": ("transactions.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["review_status"] == "ready"
    assert uploaded.json()["file_type"] == "transaction_csv"
    assert uploaded.json()["row_count"] == 1

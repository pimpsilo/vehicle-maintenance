import io
from datetime import date
from fastapi.testclient import TestClient
from app.models.vehicle import Vehicle

def test_document_attachment_multi_format_lifecycle(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create a Document
    doc_res = client.post(
        "/api/v1/documents",
        json={
            "vehicle_id": sample_vehicle.id,
            "doc_type": "REGISTRATION",
            "document_number": "REG-TEST-999",
            "issuer": "CA DMV",
            "effective_date": "2024-01-01",
            "expiration_date": "2025-01-01",
            "lead_alert_days": 30
        }
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # 2. Upload PDF
    pdf_content = b"%PDF-1.4 sample vehicle registration certificate"
    pdf_upload = client.post(
        f"/api/v1/documents/{doc_id}/attachment",
        files={"file": ("registration_2024.pdf", io.BytesIO(pdf_content), "application/pdf")}
    )
    assert pdf_upload.status_code == 200
    assert pdf_upload.json()["file_name"] == "registration_2024.pdf"
    assert pdf_upload.json()["has_attachment"] is True

    # 3. Download PDF
    download_res = client.get(f"/api/v1/documents/{doc_id}/attachment")
    assert download_res.status_code == 200
    assert download_res.content == pdf_content
    assert download_res.headers["content-type"] == "application/pdf"

    # 4. Upload PNG image
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    png_upload = client.post(
        f"/api/v1/documents/{doc_id}/attachment",
        files={"file": ("insurance_card.png", io.BytesIO(png_content), "image/png")}
    )
    assert png_upload.status_code == 200
    assert png_upload.json()["file_name"] == "insurance_card.png"

    # 5. Upload Spreadsheets (XLSX)
    xlsx_content = b"PK\x03\x04fake xlsx binary spreadsheet data"
    xlsx_upload = client.post(
        f"/api/v1/documents/{doc_id}/attachment",
        files={"file": ("tax_deductions.xlsx", io.BytesIO(xlsx_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert xlsx_upload.status_code == 200
    assert xlsx_upload.json()["file_name"] == "tax_deductions.xlsx"

    # 6. Delete attachment
    del_res = client.delete(f"/api/v1/documents/{doc_id}/attachment")
    assert del_res.status_code == 200
    assert del_res.json()["has_attachment"] is False

def test_reference_doc_attachment_formats(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create Reference Doc
    guide_res = client.post(
        "/api/v1/reference-docs",
        json={
            "vehicle_id": sample_vehicle.id,
            "title": "2GR-FE Wiring Schematic & Pinout",
            "doc_category": "WIRING_DIAGRAM",
            "difficulty": "ADVANCED",
            "source_name_or_url": "Toyota TIS",
            "step_by_step_instructions": "Refer to attached high-res TIF schematic diagram"
        }
    )
    assert guide_res.status_code == 201
    guide_id = guide_res.json()["id"]

    # 2. Upload TIF diagram
    tif_content = b"II*\x00fake tif image binary"
    upload_res = client.post(
        f"/api/v1/reference-docs/{guide_id}/attachment",
        files={"file": ("wiring_diagram.tif", io.BytesIO(tif_content), "image/tiff")}
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["file_name"] == "wiring_diagram.tif"
    assert upload_res.json()["has_attachment"] is True

    # 3. Upload Markdown guide
    md_content = b"# 2GR-FE Spark Plug Replacement Steps\n1. Disconnect intake..."
    md_upload = client.post(
        f"/api/v1/reference-docs/{guide_id}/attachment",
        files={"file": ("diy_walkthrough.md", io.BytesIO(md_content), "text/markdown")}
    )
    assert md_upload.status_code == 200
    assert md_upload.json()["file_name"] == "diy_walkthrough.md"

    # 4. Upload DOCX document
    docx_content = b"PK\x03\x04fake docx binary"
    docx_upload = client.post(
        f"/api/v1/reference-docs/{guide_id}/attachment",
        files={"file": ("service_manual.docx", io.BytesIO(docx_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert docx_upload.status_code == 200
    assert docx_upload.json()["file_name"] == "service_manual.docx"

def test_service_record_receipt_upload(client: TestClient, sample_vehicle: Vehicle):
    # 1. Create service record
    rec_res = client.post(
        "/api/v1/maintenance/records",
        json={
            "vehicle_id": sample_vehicle.id,
            "service_name": "Synthetic Oil Change 0W-20",
            "completed_mileage": 105500,
            "completed_date": date.today().isoformat(),
            "performed_by_type": "DIY",
            "parts_cost": 35.50
        }
    )
    assert rec_res.status_code == 201
    rec_id = rec_res.json()["id"]

    # 2. Attach JPG photo of receipt
    jpg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF receipt photo"
    upload_res = client.post(
        f"/api/v1/maintenance/records/{rec_id}/attachment",
        files={"file": ("walmart_oil_receipt.jpg", io.BytesIO(jpg_content), "image/jpeg")}
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["file_name"] == "walmart_oil_receipt.jpg"
    assert upload_res.json()["has_attachment"] is True

    # 3. Download receipt
    dl_res = client.get(f"/api/v1/maintenance/records/{rec_id}/attachment")
    assert dl_res.status_code == 200
    assert dl_res.content == jpg_content

def test_rejected_unsupported_file_extension(client: TestClient, sample_vehicle: Vehicle):
    # Create document
    doc_res = client.post(
        "/api/v1/documents",
        json={
            "vehicle_id": sample_vehicle.id,
            "doc_type": "TITLE",
            "document_number": "TIT-1234",
            "issuer": "DMV",
            "effective_date": "2024-01-01",
            "expiration_date": "2030-01-01"
        }
    )
    doc_id = doc_res.json()["id"]

    # Try uploading an unsupported .exe file
    bad_upload = client.post(
        f"/api/v1/documents/{doc_id}/attachment",
        files={"file": ("malicious_program.exe", io.BytesIO(b"MZ..."), "application/octet-stream")}
    )
    assert bad_upload.status_code == 400
    assert "File type not supported" in bad_upload.json()["detail"]

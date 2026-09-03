from typing import Optional
import io
import qrcode
import qrcode.image.svg
from app.config import settings

class QRService:
    @staticmethod
    def get_vehicle_portal_url(vehicle_id: int, base_url: Optional[str] = None) -> str:
        resolved_base = (base_url or settings.base_public_url).rstrip("/")
        return f"{resolved_base}/v/{vehicle_id}"

    @staticmethod
    def generate_qr_svg(vehicle_id: int, base_url: Optional[str] = None) -> str:
        url = QRService.get_vehicle_portal_url(vehicle_id, base_url=base_url)
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(url, image_factory=factory, box_size=10, border=2)
        stream = io.BytesIO()
        img.save(stream)
        return stream.getvalue().decode("utf-8")

    @staticmethod
    def generate_qr_png_bytes(vehicle_id: int, base_url: Optional[str] = None) -> bytes:
        url = QRService.get_vehicle_portal_url(vehicle_id, base_url=base_url)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()


from odoo import api, fields, models
from socket import create_connection
import logging
import json
import base64
import io
from PIL import Image, ImageOps

_logger = logging.getLogger(__name__)

def escpos_send(ip: str, data: bytes, port: int = 9100, timeout: float = 3.0):
    with create_connection((ip, port), timeout=timeout) as s:
        s.sendall(data)

def escpos_text(lines, codepage: int = 0, cut=False):
    ESC, GS = b'\x1b', b'\x1d'
    buf = bytearray()
    buf += ESC + b'@' # init
    buf += ESC + b't' + bytes([codepage]) # codepage 0 (CP437) by default
    for line in lines:
        buf += (line or '').encode('cp437', errors='replace') + b'\n'
    buf += b'\n\n'
    if cut:
        buf += GS + b'V' + b'\x41' + b'\x03' # full cut
    return bytes(buf)

def escpos_image_from_png(png_bytes):
    """Convert a PNG byte string into ESC/POS raster graphics."""
    with Image.open(io.BytesIO(png_bytes)) as img:
        img = img.convert("L")
        img = img.resize(img.size, Image.NEAREST)            # grayscale
        img = ImageOps.invert(img)        # make dark modules “on”
        img = img.point(lambda x: 0 if x < 150 else 255, mode="1")  # threshold to B/W

        width, height = img.size
        if width % 8:
            pad = 8 - (width % 8)
            img = ImageOps.expand(img, border=(0, 0, pad, 0), fill=255)
            width += pad

        pixels = img.tobytes()
        row_bytes = width // 8
        escpos_data = bytearray()
        
        
       
        escpos_data += b"\x1d\x76\x30\x00"
        escpos_data += row_bytes.to_bytes(2, "little")
        escpos_data += height.to_bytes(2, "little")

        for y in range(height):
            row_start = y * row_bytes
            escpos_data += pixels[row_start:row_start + row_bytes]

    return bytes(escpos_data)

class PosPrintJob(models.Model):
    _name = 'pos.print.job'
    _description = 'POS Print Job'


    order_id = fields.Many2one('pos.order', required=True, ondelete='cascade', index=True)
    payload = fields.Text(required=True)           
    printer_ip = fields.Char(required=True)
    status = fields.Selection(
        [('pending', 'Pending'), ('done', 'Done'), ('error', 'Error')],
        default='pending', index=True
    )
    attempts = fields.Integer(default=0)
    error = fields.Text()

    @api.model
    def cron_process_jobs(self, batch=10, codepage=0):
        jobs = self.search([('status', '=', 'pending')], limit=batch, order='id asc')
        for job in jobs:
            try:
                job_data = json.loads(job.payload or "{}")
                lines = list(job_data.get("lines", []))
                end_line = job_data.get("end_line")

                
                data = bytearray()
                data += escpos_text(lines, codepage=codepage)


                if not lines and not end_line:
                    job.write({
                        "status": "error",
                        "attempts": job.attempts + 1,
                        "error": "No printable lines in payload",
                    })
                    continue

                printable_content = "\n".join(lines)

                _logger.info("🧾 Printing job %s to printer",
                            job.id, job.printer_ip, printable_content)

                
                CUT = b"\x1dV\x41\x03"
                data = bytearray()
                data += escpos_text(lines, codepage=codepage)

            
                if job_data.get("verification_qr"):
                    qr_bytes = base64.b64decode(job_data["verification_qr"])
                    data += escpos_image_from_png(qr_bytes)
                    data += escpos_text([""], codepage=codepage)  # spacer after QR

                if end_line:
                    data += escpos_text([end_line], codepage=codepage)
                data += CUT

                escpos_send(job.printer_ip, bytes(data))
                job.write({"status": "done"})
            except Exception as e:
                job.write({
                    'status': 'error',
                    'attempts': job.attempts + 1,
                    'error': str(e),
                })


"""Private file storage, validated uploads and generated PDFs. No public MEDIA routes."""
import hashlib
import io
import math
import struct
import uuid
import warnings
from pathlib import PurePosixPath, PureWindowsPath
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import connection


def storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def private_open(name):
    if not name.startswith(connection.schema_name + '/'):
        raise ValidationError('Document belongs to another tenant.')
    return storage().open(name, 'rb')


def save_bytes(folder, filename, content):
    name = storage().save(f'{connection.schema_name}/{folder}/{filename}', ContentFile(content))
    return name, hashlib.sha256(content).hexdigest()


def save_attachment(order, uploaded, kind, actor):
    from PIL import Image
    from .models import CaseAttachment
    if uploaded is None or uploaded.size > 25 * 1024 * 1024 or uploaded.size <= 0:
        raise ValidationError('Upload a non-empty file of at most 25 MB.')
    content = uploaded.read(25 * 1024 * 1024 + 1)
    name = PurePosixPath(PureWindowsPath(uploaded.name).name).name[:255]
    extension = PurePosixPath(name).suffix.lower()
    mime = None
    if kind == 'STL' or (kind == 'DESIGN' and extension == '.stl'):
        if extension != '.stl':
            raise ValidationError('STL uploads must use the .stl extension.')
        valid = False
        if len(content) >= 84:
            count = struct.unpack('<I', content[80:84])[0]
            if count > 0 and len(content) == 84 + count * 50:
                valid = all(math.isfinite(v) for offset in range(84, len(content), 50)
                            for v in struct.unpack('<12f', content[offset:offset + 48]))
        if not valid:
            try:
                text = content.decode('ascii')
                vertices = [line.split()[1:] for line in text.splitlines() if line.strip().startswith('vertex ')]
                valid = text.lstrip().startswith('solid') and 'endsolid' in text and bool(vertices) and len(vertices) % 3 == 0
                valid = valid and all(len(v) == 3 and all(math.isfinite(float(x)) for x in v) for v in vertices)
            except (UnicodeError, ValueError):
                valid = False
        if not valid:
            raise ValidationError('The uploaded data is not a valid finite STL mesh.')
        mime = 'model/stl'
    elif kind in {'PHOTO', 'DESIGN'} and extension in {'.png', '.jpg', '.jpeg'}:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    if image.format not in {'PNG', 'JPEG'} or image.width * image.height > 20000000:
                        raise ValueError('Unsupported image')
                    mime = 'image/png' if image.format == 'PNG' else 'image/jpeg'
                    image.verify()
        except Exception as exc:
            raise ValidationError('Upload a valid JPEG or PNG photograph/design.') from exc
    elif kind == 'DESIGN' and extension == '.pdf' and content.startswith(b'%PDF-'):
        mime = 'application/pdf'
    if mime is None:
        raise ValidationError('Choose STL, PHOTO (JPEG/PNG), or DESIGN (PDF/STL/JPEG/PNG).')
    stored, digest = save_bytes(f'cases/{order.pk}', uuid.uuid4().hex + extension, content)
    try:
        attachment = CaseAttachment.objects.create(prescription=order, kind=kind, storage_name=stored,
            original_name=name, sha256=digest, byte_size=len(content), content_type=mime, uploaded_by=actor)
    except Exception:
        storage().delete(stored)
        raise
    order.save(update_fields=['updated_at'])
    return attachment


def qr_png(order):
    import qrcode
    from .case_commands import qr_token
    output = io.BytesIO()
    qrcode.make(qr_token(order)).save(output, format='PNG')
    return output.getvalue()


def pdf_document(title, lines):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    flow = [Paragraph(escape(title), styles['Title']), Spacer(1, 15)]
    for line in lines:
        if isinstance(line, list):
            rows = [[Paragraph(escape(str(cell)), styles['BodyText']) for cell in row] for row in line]
            table = Table(rows, repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), .3, colors.grey),
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2e8f0')), ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),7), ('RIGHTPADDING',(0,0),(-1,-1),7)]))
            flow.append(table)
        else:
            flow.append(Paragraph(escape(str(line)), styles['BodyText']))
        flow.append(Spacer(1, 10))
    SimpleDocTemplate(output, pagesize=A4, title=title, author='Cabinet 2.0').build(flow)
    return output.getvalue()


def delivery_slip(order):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    output = io.BytesIO()
    page = canvas.Canvas(output)
    page.setTitle('Bon de livraison ' + str(order.pk))
    page.drawString(45, 800, 'Cabinet 2.0 - Bon de livraison')
    for y, text in [(770, str(order.pk)), (750, order.patient_ref), (730, order.partner_clinic.name if order.partner_clinic else order.dentist_name)]:
        page.drawString(45, y, text)
    address = order.partner_clinic.pickup_address if order.partner_clinic else ''
    for i, line in enumerate(address.splitlines()[:8]):
        page.drawString(45, 710 - i * 16, line[:100])
    page.drawImage(ImageReader(io.BytesIO(qr_png(order))), 45, 400, 180, 180)
    page.showPage()
    page.save()
    return output.getvalue()

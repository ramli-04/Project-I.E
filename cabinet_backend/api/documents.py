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


def document_identity():
    from .models import LaboratoryProfile
    from customers.models import Client
    profile = LaboratoryProfile.objects.filter(pk=1).first() or LaboratoryProfile()
    name = profile.legal_name
    if not name:
        name = (getattr(connection.tenant, 'name', '') or
                Client.objects.filter(schema_name=connection.schema_name).values_list('name', flat=True).first() or 'Laboratoire')
    return {'name': name, 'address': profile.address, 'city': profile.city,
            'phone': profile.phone, 'email': profile.email,
            'footer': ' \u00b7 '.join(f'{label} {value}' for label, value in [
                ('ICE', profile.ice), ('IF', profile.identifiant_fiscal),
                ('RC', profile.registre_commerce), ('Patente', profile.patente)] if value)}


def pdf_document(title, lines, *, images=(), trailer=()):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    identity = document_identity()
    flow = [Paragraph(escape('Gestion Labo \u00b7 ' + identity['name']), styles['Heading1'])]
    for line in [*identity['address'].splitlines(), identity['city'],
                 ' \u00b7 '.join(value for value in [identity['phone'], identity['email']] if value)]:
        if line:
            flow.append(Paragraph(escape(line), styles['BodyText']))
    flow += [Spacer(1, 15), Paragraph(escape(title), styles['Title']), Spacer(1, 15)]
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
    flow.extend(Image(io.BytesIO(content), width=180, height=180, hAlign='LEFT') for content in images)
    for line in trailer:
        if isinstance(line, list):
            rows = [[Paragraph(escape(str(cell)).replace('\n', '<br/>'), styles['BodyText']) for cell in row] for row in line]
            table = Table(rows, colWidths=[250, 250], hAlign='LEFT')
            table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), .3, colors.grey), ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e2e8f0')), ('BOTTOMPADDING',(0,1),(-1,1),40)]))
            flow += [Spacer(1, 10), table]
        else:
            flow.append(Paragraph(escape(str(line)), styles['Italic']))

    def footer(page, document):
        if not identity['footer']:
            return
        page.saveState()
        paragraph = Paragraph(escape(identity['footer']), styles['Normal'])
        _, height = paragraph.wrap(document.width, 60)
        paragraph.drawOn(page, document.leftMargin, 25)
        page.restoreState()

    SimpleDocTemplate(output, pagesize=A4, title=title, author='Gestion Labo',
        leftMargin=45, rightMargin=45, topMargin=40, bottomMargin=85).build(
            flow, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def _fr_date(value):
    from django.utils import timezone
    if not value:
        return 'à confirmer'
    if hasattr(value, 'hour'):
        value = timezone.localtime(value)
        return value.strftime('%d/%m/%Y %H:%M')
    return value.strftime('%d/%m/%Y')


def delivery_slip(order):
    """Delivery note for newly generated documents: labelled identity, contents, dates,
    lot traceability for a custom-made device and signature boxes."""
    from django.utils import timezone
    clinic = order.partner_clinic
    address = ' '.join((clinic.pickup_address if clinic else '').splitlines()[:8]) or '—'
    info = [['Champ', 'Valeur'],
            ['N° de dossier', str(order.pk)], ['Référence patient', order.patient_ref],
            ['Cabinet', clinic.name if clinic else '—'], ['Adresse de livraison', address],
            ['Dentiste', order.dentist_name or '—']]
    items = list(order.clinical_items.values_list('tooth_number', 'function', 'form', 'material', 'shade'))
    if not items and order.tooth_number:
        items = [(order.tooth_number, '—', '—', order.material or '—', order.shade or '—')]
    contents = [['Dent', 'Fonction', 'Forme', 'Matériau', 'Teinte'], *[[str(cell) for cell in row] for row in items]]
    shipped = (order.audit_history.filter(new_status='EN_ROUTE_CABINET').order_by('-created_at')
               .values_list('created_at', flat=True).first())
    dates = [['Date', 'Valeur'], ['Édité le', _fr_date(timezone.now())],
             ['Expédié le', _fr_date(shipped)], ['Livraison prévue', _fr_date(order.delivery_date)]]
    lots = [[lot.code, lot.machine.name if lot.machine_id else '—'] for lot in order.production_lots.select_related('machine')]
    trace = [['Lot de production', 'Machine'], *(lots or [['Aucun lot lié', '—']])]
    signatures = [['Remis par (coursier)', 'Reçu par (cabinet)'],
                  ['Nom :\nDate / heure :\nSignature :', 'Nom :\nDate / heure :\nSignature et cachet :']]
    return pdf_document('Bon de livraison', ['Identification', info, 'Contenu de la livraison', contents,
                                             'Dates', dates, 'Traçabilité (dispositif sur mesure)', trace],
                        images=[qr_png(order)],
                        trailer=['Scanner ce QR pour confirmer la remise.', signatures])

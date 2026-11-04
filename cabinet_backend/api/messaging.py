"""External delivery adapters. Ambiguous sends require reconciliation, never blind replay."""
import json
import uuid
from urllib import request as http_request
from urllib.parse import urlparse

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from .models import MessageDelivery, InvoiceDocument, CreditDocument
from .documents import private_open


def notification_document(notification):
    if notification.kind == 'INVOICE_READY':
        document = InvoiceDocument.objects.select_related('invoice').get(invoice_id=notification.payload['invoice_id'])
        return document.invoice.number + '.pdf', document.storage_name
    if notification.kind == 'CREDIT_READY':
        document = CreditDocument.objects.get(credit_note_id=notification.payload['credit_id'])
        return 'avoir-' + str(document.credit_note_id) + '.pdf', document.storage_name
    return None


def post_json(url, body):
    request = http_request.Request(url, data=json.dumps(body).encode(), method='POST', headers={
        'Authorization': 'Bearer ' + settings.WHATSAPP_ACCESS_TOKEN, 'Content-Type': 'application/json',
    })
    with http_request.urlopen(request, timeout=10) as response:
        return json.load(response)


def send_whatsapp(delivery, text, document):
    url = settings.WHATSAPP_SEND_URL
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'graph.facebook.com' or not parsed.path.endswith('/messages'):
        raise ValueError('Configure an HTTPS Meta Graph /messages endpoint.')
    body = {'messaging_product': 'whatsapp', 'to': delivery.destination, 'biz_opaque_callback_data': str(delivery.pk)}
    if document:
        filename, stored = document
        boundary = uuid.uuid4().hex
        with private_open(stored) as stream:
            content = stream.read()
        multipart = (f'--{boundary}\r\nContent-Disposition: form-data; name="messaging_product"\r\n\r\nwhatsapp\r\n'
                     f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\napplication/pdf\r\n'
                     f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n').encode()
        multipart += content + f'\r\n--{boundary}--\r\n'.encode()
        upload = http_request.Request(url[:-len('/messages')] + '/media', data=multipart, method='POST', headers={
            'Authorization': 'Bearer ' + settings.WHATSAPP_ACCESS_TOKEN,
            'Content-Type': 'multipart/form-data; boundary=' + boundary})
        with http_request.urlopen(upload, timeout=10) as response:
            media_id = json.load(response)['id']
        body.update({'type': 'document', 'document': {'id': media_id, 'filename': filename, 'caption': text[:1024]}})
    else:
        body.update({'type': 'text', 'text': {'body': text[:4000]}})
    return post_json(url, body)['messages'][0]['id']


def deliver_pending():
    if not settings.EXTERNAL_DELIVERY_ENABLED:
        return {'status': 'DISABLED', 'sent': 0}
    ids = list(MessageDelivery.objects.filter(status__in=['PENDING', 'WAIT_CONFIGURATION'], next_attempt_at__lte=timezone.now())
               .order_by('next_attempt_at', 'pk').values_list('pk', flat=True)[:10])
    sent = 0
    for identity in ids:
        with transaction.atomic():
            delivery = MessageDelivery.objects.select_for_update().select_related('notification').get(pk=identity)
            if delivery.status not in {'PENDING', 'WAIT_CONFIGURATION'}:
                continue
            configured = bool(settings.EMAIL_HOST) if delivery.channel == 'EMAIL' else bool(settings.WHATSAPP_SEND_URL and settings.WHATSAPP_ACCESS_TOKEN)
            if not configured:
                delivery.status, delivery.last_error = 'WAIT_CONFIGURATION', 'Delivery provider is not configured.'
                delivery.save(update_fields=['status', 'last_error'])
                continue
            delivery.status, delivery.attempts = 'SENDING', delivery.attempts + 1
            delivery.save(update_fields=['status', 'attempts'])
        # Commit SENDING before contacting the provider. A crash cannot trigger an automatic duplicate send.
        try:
            notification = delivery.notification
            text = f'Cabinet 2.0 - {notification.kind} - Cas {notification.prescription_id}'
            document = notification_document(notification)
            if delivery.channel == 'EMAIL':
                message = EmailMessage('Cabinet 2.0 - ' + notification.kind, text,
                    settings.DEFAULT_FROM_EMAIL, [delivery.destination],
                    headers={'Message-ID': f'<{delivery.pk}@cabinet2.local>'})
                if document:
                    with private_open(document[1]) as stream:
                        message.attach(document[0], stream.read(), 'application/pdf')
                if message.send(fail_silently=False) != 1:
                    raise RuntimeError('Provider did not confirm acceptance.')
                reference = str(delivery.pk)
            else:
                reference = send_whatsapp(delivery, text, document)
        except Exception as exc:
            delivery.status = 'UNKNOWN'
            delivery.last_error = f'{type(exc).__name__}: delivery outcome requires operator reconciliation.'
        else:
            delivery.status, delivery.sent_at, delivery.provider_reference = 'SENT', timezone.now(), reference
            delivery.last_error = ''
            sent += 1
        delivery.save(update_fields=['status', 'sent_at', 'provider_reference', 'last_error'])
    return {'status': 'PROCESSED', 'sent': sent}

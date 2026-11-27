import io
import re
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIClient
from customers.models import PlatformAccount
from .models import (LaboratoryProfile, Prescription, PartnerClinic, FinanceInvoice,
                     InvoiceDocument, CreditNote, CreditDocument, TaskOutbox)
from .documents import pdf_document, delivery_slip, save_bytes
from .test_support import WorkflowFixtures
from .billing import close_period, issue_credit
from .tasks import generate_invoice_pdf_task, generate_credit_note_pdf_task


def pdf_text(content):
    # These fixtures disable compression and use ReportLab's WinAnsi text draws.
    # Join adjacent Tj operands so escaped HTML fragments are tested as visible text.
    def unescape(match):
        value=match.group(1)
        if value.isdigit():
            return bytes([int(value,8)])
        return {b'n':b'\n',b'r':b'\r',b't':b'\t',b'b':b'\b',b'f':b'\f'}.get(value,value)
    parts=re.findall(rb'\(((?:\\.|[^\\)])*)\)\s*Tj',content)
    return b''.join(re.sub(rb'\\([0-7]{1,3}|.)',unescape,part) for part in parts).decode('cp1252')


@override_settings(OUTBOX_PUBLISH_ON_COMMIT=False, EXTERNAL_DELIVERY_ENABLED=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LaboratoryProfileTests(WorkflowFixtures, TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = 'Identity fallback lab'

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.files = tempfile.TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        media = override_settings(PRIVATE_MEDIA_ROOT=self.files.name)
        media.enable()
        self.addCleanup(media.disable)
        with schema_context('public'):
            self.manager = get_user_model().objects.create_user(username='profile-manager', is_superuser=True)
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.manager)
        self.url = '/api/laboratory-profile/'
        self.data = {'legal_name':'Laboratoire Test Atlas','address':'12 Rue Synthetic',
                     'city':'Ville Test','phone':'0000000000','email':'demo@example.invalid',
                     'ice':'000000000000000','identifiant_fiscal':'IF123',
                     'registre_commerce':'RC456','patente':'PAT789'}

    def test_get_empty_defaults_is_read_only_and_uncached(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['legal_name'],'')
        self.assertIsNone(response.json()['updated_at'])
        self.assertEqual(LaboratoryProfile.objects.count(),0)
        self.assertEqual(response['Cache-Control'],'no-store')

    def test_manager_updates_singleton_and_server_attribution(self):
        response = self.client.put(self.url,{**self.data,'id':2,'updated_by':'forged'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['id'],1)
        self.assertEqual(response.data['updated_by'],f'user:{self.manager.pk}:profile-manager')
        self.assertIsNotNone(response.data['updated_at'])
        response = self.client.put(self.url,{**self.data,'legal_name':'Updated lab'},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(LaboratoryProfile.objects.count(),1)
        self.assertEqual(self.client.get(self.url).data['legal_name'],'Updated lab')

    def test_ice_accepts_blank_or_fifteen_ascii_digits_and_rejects_other_formats(self):
        for invalid in ['123','12345678901234A','\uff10'*15,'000000000000000\n']:
            with self.subTest(invalid=repr(invalid)):
                response = self.client.put(self.url,{**self.data,'ice':invalid},format='json')
                self.assertEqual(response.status_code,400,response.data)
                self.assertIn('ICE must contain exactly 15 digits.',str(response.data))
        self.assertEqual(LaboratoryProfile.objects.count(),0)
        for valid in ['', '000000000000000','123456789012345']:
            response = self.client.put(self.url,{**self.data,'ice':valid},format='json')
            self.assertEqual(response.status_code,200,response.data)
        with self.assertRaises(ValidationError):
            LaboratoryProfile(ice='bad').full_clean()

    def test_database_enforces_singleton_and_ice_even_for_direct_writes(self):
        LaboratoryProfile.objects.create()
        with self.assertRaises(IntegrityError),transaction.atomic():
            LaboratoryProfile.objects.bulk_create([LaboratoryProfile(id=2)])
        with self.assertRaises(IntegrityError),transaction.atomic():
            LaboratoryProfile.objects.filter(pk=1).update(ice='invalid')
        self.assertEqual(LaboratoryProfile.objects.get().ice,'')

    def test_role_matrix_and_missing_tenant_membership(self):
        for role in ['MANAGER','COMPTABILITE','RECEPTION','CAO','FAO','QUALITE','COURIER','DENTIST']:
            with self.subTest(role=role):
                with schema_context('public'):
                    account = PlatformAccount.objects.create(name='Profile '+role,login_key='profile-'+role.lower(),
                        role=role if role in {'DENTIST','COURIER'} else 'LAB',
                        workstation_role=role if role not in {'DENTIST','COURIER'} else 'MANAGER',
                        laboratory=self.tenant if role!='DENTIST' else None)
                self.client.force_authenticate(account)
                self.assertEqual(self.client.get(self.url).status_code,200 if role in {'MANAGER','COMPTABILITE'} else 403)
                self.assertEqual(self.client.put(self.url,self.data,format='json').status_code,200 if role=='MANAGER' else 403)
        with schema_context('public'):
            unassigned=PlatformAccount.objects.create(name='Unassigned manager',login_key='unassigned-profile-manager',
                                                      role='LAB',workstation_role='MANAGER')
        self.client.force_authenticate(unassigned)
        self.assertEqual(self.client.get(self.url).status_code,403)
        self.assertEqual(self.client.put(self.url,self.data,format='json').status_code,403)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code,401)

    def test_unsupported_mutation_methods_cannot_remove_profile(self):
        self.assertEqual(self.client.put(self.url,self.data,format='json').status_code,200)
        for method in ['post','patch','delete']:
            self.assertEqual(getattr(self.client,method)(self.url,{},format='json').status_code,405)
        self.assertEqual(LaboratoryProfile.objects.count(),1)

    def pdf_bytes(self,title='Facture',lines=None):
        with patch('reportlab.rl_config.pageCompression',0):
            return pdf_document(title,lines or ['Synthetic document'])

    def test_new_documents_print_identity_and_repeat_identifiers_on_each_page(self):
        self.assertEqual(self.client.put(self.url,self.data,format='json').status_code,200)
        pdf=self.pdf_bytes(lines=['Synthetic row '+str(i) for i in range(150)])
        for expected in ['Gestion Labo','Laboratoire Test Atlas','12 Rue Synthetic','Ville Test',
                         '0000000000','ICE 000000000000000','IF IF123','RC RC456','Patente PAT789']:
            self.assertIn(expected,pdf_text(pdf))
        self.assertGreater(pdf.count(b'ICE 000000000000000'),1)
        self.assertIn(b'/Author (Gestion Labo)',pdf)
        self.assertNotIn(b'Cabinet 2.0',pdf)
        order=Prescription.objects.create(patient_ref='PROFILE-SLIP',dentist_name='Synthetic dentist',
            tooth_number=11,shade='A2',material='Zircone',disinfected=True,impression_type='NUMERIQUE')
        with patch('reportlab.rl_config.pageCompression',0):slip=delivery_slip(order)
        self.assertIn(b'Laboratoire Test Atlas',slip)
        self.assertIn(b'PROFILE-SLIP',slip)
        self.assertIn(b'ICE 000000000000000',slip)
        # Step 8.8: labelled delivery note with contents, dates, traceability and signatures.
        text=pdf_text(slip)
        for expected in ['N° de dossier','Référence patient','Contenu de la livraison','Zircone','A2',
                         'Livraison prévue','Expédié le','Aucun lot lié','Scanner ce QR pour confirmer la remise.',
                         'Remis par (coursier)','Reçu par (cabinet)','Signature :']:
            self.assertIn(expected,text)

    def test_missing_or_empty_profile_falls_back_without_creating_rows(self):
        pdf=self.pdf_bytes()
        self.assertIn(b'Identity fallback lab',pdf)
        self.assertNotIn(b'ICE ',pdf)
        self.assertEqual(LaboratoryProfile.objects.count(),0)
        LaboratoryProfile.objects.create()
        self.assertIn(b'Identity fallback lab',self.pdf_bytes())
        self.client.put(self.url,{'legal_name':'<Atlas & Fils>'},format='json')
        self.assertIn('<Atlas & Fils>',pdf_text(self.pdf_bytes()))

    def test_existing_invoice_and_credit_pdf_bytes_and_rows_remain_immutable(self):
        clinic=PartnerClinic.objects.create(name='Profile historical clinic',pickup_address='Synthetic',contact_phone='000')
        with patch('django.utils.timezone.now',return_value=datetime(2026,1,1,12,tzinfo=timezone.utc)):
            order=Prescription.objects.create(patient_ref='PROFILE-LEGACY',dentist_name='Synthetic dentist',
                tooth_number=11,shade='A2',material='Zircone',disinfected=True,impression_type='NUMERIQUE',
                partner_clinic=clinic,total_price='1500.00',base_amount='1500.00',accepted=True,intake_version=1)
        with patch('django.utils.timezone.now',return_value=datetime(2026,10,15,12,tzinfo=timezone.utc)):
            self.deliver_case(order,pin=order._new_delivery_pin)
        invoice=close_period(order.statement_line.period_id,'test:accountant')
        credit=issue_credit(invoice.pk,order.pk,'100','Synthetic adjustment','test:accountant',uuid.uuid4())
        from reportlab.pdfgen.canvas import Canvas
        def legacy(title):
            output=io.BytesIO()
            page=Canvas(output)
            page.setAuthor('Cabinet 2.0')
            page.drawString(40,800,'Cabinet 2.0 '+title)
            page.save()
            return output.getvalue()
        old_invoice,old_credit=legacy('invoice'),legacy('credit')
        name,digest=save_bytes('invoices','legacy-invoice.pdf',old_invoice)
        InvoiceDocument.objects.create(invoice=invoice,storage_name=name,sha256=digest)
        name,digest=save_bytes('credits','legacy-credit.pdf',old_credit)
        CreditDocument.objects.create(credit_note=credit,storage_name=name,sha256=digest)
        before=[list(model.objects.values()) for model in [FinanceInvoice,InvoiceDocument,CreditNote,CreditDocument]]
        self.assertEqual(self.client.put(self.url,self.data,format='json').status_code,200)
        generate_invoice_pdf_task(self.tenant.schema_name,order.pk)
        event=TaskOutbox.objects.get(event_type='CREDIT',prescription=order,payload__credit_id=str(credit.pk))
        generate_credit_note_pdf_task(self.tenant.schema_name,order.pk,str(event.pk))
        self.assertEqual(b''.join(self.client.get(f'/api/billing/invoices/{invoice.pk}/pdf/').streaming_content),old_invoice)
        self.assertEqual(b''.join(self.client.get(f'/api/billing/credit-notes/{credit.pk}/pdf/').streaming_content),old_credit)
        self.assertEqual([list(model.objects.values()) for model in [FinanceInvoice,InvoiceDocument,CreditNote,CreditDocument]],before)

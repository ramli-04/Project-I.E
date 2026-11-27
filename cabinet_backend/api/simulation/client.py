"""Real DRF routes/middleware and bearer authentication, in this clock's process."""
from datetime import timedelta
import uuid
from rest_framework.test import APIClient
from django.utils import timezone
from django.db import connection
from django_tenants.utils import tenant_context
from django.core.files.uploadedfile import SimpleUploadedFile
from customers.authentication import issue_session

STL = b'solid sim\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid sim\n'


class SimClient:
    def __init__(self):
        self.sessions = {}
        self.calls = 0

    def client(self, account, host):
        now = timezone.now()
        previous = self.sessions.get(account.pk)
        if not previous or previous[0] <= now:
            token = issue_session(account)
            previous = (now+timedelta(hours=11), token)
            self.sessions[account.pk] = previous
        client = APIClient(HTTP_HOST=host)
        client.credentials(HTTP_AUTHORIZATION='Bearer '+previous[1])
        return client

    def request(self, account, host, method, path, data=None, *, expected=200, multipart=False):
        self.calls += 1
        client = self.client(account, host)
        headers = {'HTTP_IDEMPOTENCY_KEY':str(uuid.uuid4())} if method.lower() not in {'get','head','options'} else {}
        # Tenant middleware changes the connection; restore the actor loop's context afterward.
        with tenant_context(connection.tenant):
            response = getattr(client, method.lower())(path, data or {}, format='multipart' if multipart else 'json', **headers)
        if expected is not None and response.status_code != expected:
            # Never log a response body: creation/PIN commands contain one-time secrets.
            error=response.json()
            detail=error.get('detail') or error.get('error') if isinstance(error,dict) else (error[0] if isinstance(error,list) and len(error)==1 and isinstance(error[0],str) and response.status_code==400 else '')
            safe=detail if isinstance(detail,str) and len(detail)<240 else ''
            raise RuntimeError(f'SIM HTTP {response.status_code} (expected {expected}): {method} {path}; {safe}')
        return response

    def json(self, account, host, method, path, data=None, expected=200):
        return self.request(account,host,method,path,data,expected=expected).json()

    def command(self, account, host, order, action, data=None, expected=200, dentist=False, schema=None):
        path = (f'/platform/dentist/orders/{schema}/{order}/command/' if dentist
                else f'/api/prescriptions/{order}/command/')
        return self.json(account,host,'post',path,{'action':action,'data':data or {}},expected)

    def upload(self, account, host, order, kind, photo=False):
        if photo:
            import io
            from PIL import Image
            output=io.BytesIO()
            Image.new('RGB',(2,2),(50,100,150)).save(output,format='PNG')
            file=SimpleUploadedFile('SIM-evidence.png',output.getvalue(),content_type='image/png')
        else:
            file=SimpleUploadedFile('SIM-mesh.stl',STL,content_type='model/stl')
        return self.request(account,host,'post',f'/api/prescriptions/{order}/attachments/',
                            {'kind':kind,'file':file},expected=201,multipart=True).json()

    def rows(self, account, host, path, data=None):
        result=[]
        while path:
            response=self.json(account,host,'get',path,data)
            data=None
            if isinstance(response,list):
                return result+response
            result.extend(response['results'])
            path=response.get('next')
            if path:
                from urllib.parse import urlsplit
                url=urlsplit(path)
                path=url.path+('?' + url.query if url.query else '')
        return result

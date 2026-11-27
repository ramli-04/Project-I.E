"""Public deployment label; no credentials or internal addresses exposed."""
from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def environment_info(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return Response({
        'mode': 'SIMULATION' if settings.CABINET_SIMULATION else 'APPLICATION',
        'synthetic_data': settings.CABINET_SIMULATION,
        'database': 'reachable',
    })

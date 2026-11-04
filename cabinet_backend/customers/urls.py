from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.demo_login), path('logout/', views.demo_logout),
    path('laboratories/', views.laboratories),
    path('accounts/', views.accounts), path('accounts/<int:account_id>/', views.accounts),
    path('accounts/<int:account_id>/reset-password/', views.reset_password),
    path('overview/', views.overview), path('logs/', views.logs),
    path('support/', views.support), path('support/<int:ticket_id>/', views.support),
    path('dentist/orders/', views.dentist_orders),
    path('pricing/', views.pricing_catalog),
    path('dentists/', views.dentist_directory),
    path('dentist/clinics/', views.dentist_clinics),
    path('dentist/orders/<str:schema_name>/<uuid:case_id>/attachment/<uuid:attachment_id>/', views.dentist_attachment),
    path('dentist/orders/<str:schema_name>/<uuid:case_id>/attachments/<uuid:attachment_id>/', views.dentist_attachment),
    path('dentist/orders/<str:schema_name>/<uuid:case_id>/<str:operation>/', views.dentist_case_action),
]

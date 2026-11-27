"""Mutable tenant identity; issued financial evidence remains separate."""
from django.core.validators import RegexValidator
from django.db import models

ICE_ERROR = 'ICE must contain exactly 15 digits.'


class LaboratoryProfile(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    legal_name = models.CharField(max_length=255, blank=True, default='')
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=120, blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    ice = models.CharField(max_length=15, blank=True, default='',
        validators=[RegexValidator(regex=r'\A[0-9]{15}\Z', message=ICE_ERROR)])
    identifiant_fiscal = models.CharField(max_length=50, blank=True, default='')
    registre_commerce = models.CharField(max_length=50, blank=True, default='')
    patente = models.CharField(max_length=50, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name='laboratory_profile_singleton'),
            models.CheckConstraint(condition=models.Q(ice='') | models.Q(ice__regex=r'^[0-9]{15}$'),
                                   name='laboratory_profile_ice_format'),
        ]

from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Client(TenantMixin):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    auto_create_schema = True

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass


class PlatformAccount(models.Model):
    name = models.CharField(max_length=120)
    login_key = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=20, choices=[('ADMIN', 'Administrateur'), ('DENTIST', 'Dentiste'), ('LAB', 'Laboratoire'), ('COURIER', 'Coursier')])
    workstation_role = models.CharField(max_length=12, default='MANAGER', choices=[
        ('MANAGER', 'Responsable'), ('RECEPTION', 'Reception'), ('CAO', 'CAO'),
        ('FAO', 'FAO'), ('QUALITE', 'Qualite'), ('COMPTABILITE', 'Comptabilite'),
    ])
    laboratory = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    password_hash = models.CharField(max_length=255, blank=True)
    password_reset_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_staff(self):
        return False

    @property
    def is_superuser(self):
        return False

    def get_username(self):
        return self.name


class PlatformSession(models.Model):
    token_digest = models.CharField(max_length=64, unique=True)
    account = models.ForeignKey(PlatformAccount, on_delete=models.CASCADE, related_name='sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class LoginRateLimit(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window_started_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)


class AccessLog(models.Model):
    account = models.ForeignKey(PlatformAccount, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=150)
    event = models.CharField(max_length=30)
    success = models.BooleanField(default=True)
    details = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class SupportTicket(models.Model):
    account = models.ForeignKey(PlatformAccount, on_delete=models.PROTECT)
    subject = models.CharField(max_length=150)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=[('OPEN', 'Ouvert'), ('IN_PROGRESS', 'En cours'), ('RESOLVED', 'Résolu')], default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

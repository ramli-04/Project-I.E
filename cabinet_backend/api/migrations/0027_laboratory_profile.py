import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0026_payments_and_receivables')]

    operations = [
        migrations.CreateModel(
            name='LaboratoryProfile',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('legal_name', models.CharField(blank=True, default='', max_length=255)),
                ('address', models.TextField(blank=True, default='')),
                ('city', models.CharField(blank=True, default='', max_length=120)),
                ('phone', models.CharField(blank=True, default='', max_length=50)),
                ('email', models.EmailField(blank=True, default='', max_length=254)),
                ('ice', models.CharField(blank=True, default='', max_length=15,
                    validators=[django.core.validators.RegexValidator(message='ICE must contain exactly 15 digits.', regex='\\A[0-9]{15}\\Z')])),
                ('identifiant_fiscal', models.CharField(blank=True, default='', max_length=50)),
                ('registre_commerce', models.CharField(blank=True, default='', max_length=50)),
                ('patente', models.CharField(blank=True, default='', max_length=50)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.CharField(blank=True, default='', max_length=255)),
            ],
            options={'constraints': [
                models.CheckConstraint(condition=models.Q(id=1), name='laboratory_profile_singleton'),
                models.CheckConstraint(condition=models.Q(ice='') | models.Q(ice__regex='^[0-9]{15}$'),
                                       name='laboratory_profile_ice_format'),
            ]},
        ),
    ]

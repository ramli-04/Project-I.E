from datetime import timedelta
from django.utils import timezone
from .models import Equipment, StaffMember, StockItem, Inventory, MonthlyStockLossCatalog


def laboratory_alerts(today=None):
    today = today or timezone.localdate()
    deadline = today + timedelta(days=7)
    alerts = []

    def add(kind, section, item, message, date=None, reference=None, name=None):
        alerts.append({
            'id': f'{kind}-{item.pk}', 'type': kind, 'section': section,
            'resource_id': item.pk, 'name': name or getattr(item, 'name', str(item)),
            'reference': reference or getattr(item, 'reference', str(item.pk)),
            'message': message, 'due_date': date.isoformat() if date else None,
            'overdue': bool(date and date < today) if date else (kind in {'stock', 'loss'}),
        })

    def date_message(date):
        days = (date - today).days
        if days < 0:
            return f'est dépassée depuis le {date:%d/%m/%Y}'
        if days == 0:
            return 'arrive à échéance aujourd’hui'
        return f'arrive à échéance dans {days} jour(s), le {date:%d/%m/%Y}'

    for item in StockItem.objects.all():
        if item.quantity <= item.minimum_quantity:
            add('stock', 'stock', item, f'Votre stock de « {item.name} » est au seuil d’alerte ou en dessous : {item.quantity:g} {item.unit} restant(s), seuil {item.minimum_quantity:g} {item.unit}.')
        if item.expiry_date and item.expiry_date < today:
            add('expiry', 'stock', item, f'Votre stock de « {item.name} » est périmé depuis le {item.expiry_date:%d/%m/%Y}.', item.expiry_date)

    for item in Inventory.objects.all():
        if item.is_low_stock:
            add('stock', 'inventory', item,
                f'Le stock de matière « {item.material_name} » est au seuil d’alerte ou en dessous : {item.quantity:g} {item.unit} restant(s), seuil {item.alert_threshold:g} {item.unit}.',
                reference=item.material_name, name=item.material_name)

    for catalog in MonthlyStockLossCatalog.objects.filter(complete_valuation=False):
        alerts.append({
            'id': f'loss-valuation-{catalog.pk}', 'type': 'loss', 'section': 'inventory',
            'resource_id': catalog.pk, 'name': catalog.inventory_item.material_name,
            'reference': catalog.inventory_item.material_name,
            'message': f'Pertes matières de « {catalog.inventory_item.material_name} » pour {catalog.loss_month:%Y-%m} avec valorisation incomplète ({catalog.unvalued_quantity:g} {catalog.inventory_item.unit} sans coût unitaire).',
            'due_date': None,
            'overdue': True,
        })

    for item in Equipment.objects.filter(maintenance_date__lte=deadline):
        add('maintenance', 'equipment', item, f'La maintenance de votre machine « {item.name} » {date_message(item.maintenance_date)}.', item.maintenance_date)
    for item in StaffMember.objects.all():
        if item.contract_end_date and item.contract_end_date <= deadline:
            add('contract', 'staff', item, f'La date de fin du contrat de « {item.name} » {date_message(item.contract_end_date)}.', item.contract_end_date)
        if item.qualification_expiry_date and item.qualification_expiry_date <= deadline:
            add('qualification', 'staff', item, f'La validité des qualifications de « {item.name} » {date_message(item.qualification_expiry_date)}.', item.qualification_expiry_date)
    return sorted(alerts, key=lambda alert: (not alert['overdue'], alert['due_date'] or '', alert['id']))
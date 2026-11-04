from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError

BASE_PRICES = {'Zircone': Decimal('1200'), 'E-Max': Decimal('1500'), 'Céramo-Métal': Decimal('800'),
               '100% Métal': Decimal('500'), 'Provisoire Résine': Decimal('200')}
EXPRESS_RATE = Decimal('0.30')
CENT = Decimal('0.01')


def price_items(items, service, manual_surcharge=None):
    total = Decimal('0')
    for item in items:
        if item['material'] not in BASE_PRICES:
            raise ValidationError({'material': 'Choose a material from the laboratory price catalog.'})
        item['base_amount'] = BASE_PRICES[item['material']]
        total += item['base_amount']
    if service == 'NEXT_DAY' and manual_surcharge is None:
        return total, None
    surcharge = (total * EXPRESS_RATE).quantize(CENT, rounding=ROUND_HALF_UP) if service == 'EXPRESS' else Decimal('0')
    if service == 'NEXT_DAY':
        surcharge = Decimal(str(manual_surcharge)).quantize(CENT)
        if not surcharge.is_finite() or surcharge < 0:
            raise ValidationError('The manual J+1 surcharge must be non-negative.')
    return total.quantize(CENT), surcharge

"""Scenario inputs only; no alternative workflow or calendar implementation."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import random
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Africa/Casablanca')
START = datetime(2026, 11, 2, 8, tzinfo=TZ)
HOLIDAY = START.date() + timedelta(days=16)


@dataclass(frozen=True)
class Profile:
    key: str
    technicians: int
    cad: int
    fabrication: int
    daily_cases: int
    mills: int
    furnaces: int
    printers: int

    @property
    def staffing(self):
        return {'manufacturing_technicians': self.technicians, 'reception': 1,
                'quality': 1, 'total_scheduled_staff': self.technicians+2}


PROFILES = [Profile('PETIT',2,1,1,8,0,0,0), Profile('MOYEN',5,2,3,20,1,1,1),
            Profile('GRAND',10,4,6,60,2,2,2)]


def demand(scenario, seed, days=28, grand_daily=60, tiny=False, profiles=None):
    result = []
    for index, profile in enumerate(profiles or PROFILES):
        rng = random.Random(seed + PROFILES.index(profile)*10007)
        sequence = 0
        volume = grand_daily if profile.key == 'GRAND' else profile.daily_cases
        if scenario == 'mixed' and profile.key == 'MOYEN':
            volume = round(volume*1.5)
        for offset in range(days):
            day = START.date()+timedelta(days=offset)
            if day.weekday() == 6 or day == HOLIDAY or tiny and offset:
                continue
            count = 1 if tiny else max(1,round(volume*(.5 if day.weekday()==5 else 1)))
            for position in range(count):
                sequence += 1
                arrival = datetime.combine(day, time(8 if scenario != 'ramadan' else 9), TZ)
                arrival += timedelta(minutes=5)
                route = 'CONVENTIONNEL' if not profile.mills or tiny else rng.choices(
                    ['CFAO','IMPRESSION_3D','CONVENTIONNEL'],[.65,.2,.15])[0]
                service = 'STANDARD' if tiny else rng.choices(['STANDARD','EXPRESS','NEXT_DAY'],[.8,.17,.03])[0]
                material = ('100% Métal' if route == 'CONVENTIONNEL' else
                            'Provisoire Résine' if route == 'IMPRESSION_3D' else rng.choice(['Zircone','E-Max']))
                result.append({'at':arrival,'profile':profile.key,'sequence':sequence,
                    'reference':f'SIM-{profile.key}-{scenario[:3].upper()}-{sequence:05}', 'route':route,
                    'service':service,'material':material,'physical':False if tiny else rng.random()<.4,
                    'design':False if tiny or route=='CONVENTIONNEL' else rng.random()<.35,
                    'clinic_index':position%2,
                    'failures':{key:False if tiny else rng.random()<chance for key,chance in
                        [('intake',.04),('model',.02),('design',.1),('quality',.04),('fitting',.02)]}})
    return sorted(result,key=lambda row:(row['at'],row['sequence'],row['profile']))

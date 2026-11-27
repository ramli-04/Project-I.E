from pathlib import Path
import json
from django.core.management.base import BaseCommand, CommandError
from api.simulation.guards import environment_guard
from api.simulation.runner import Simulation


class Command(BaseCommand):
    help='Simulation synthétique isolée, via les vraies commandes et le planning.'

    def add_arguments(self, parser):
        parser.add_argument('--scenario',choices=['normal','ramadan','mixed'],default='normal')
        parser.add_argument('--seed',type=int,default=20261209)
        parser.add_argument('--days',type=int,default=28)
        parser.add_argument('--grand-daily',type=int,default=60)
        parser.add_argument('--tiny',action='store_true')
        parser.add_argument('--benchmark',action='store_true',help='Mesure de fonctionnement, sans preuve d’isolation finale.')
        parser.add_argument('--output',default='/demo/simulation-reports/run.json')

    def handle(self,*args,**options):
        environment_guard()
        if not 1<=options['days']<=28 or not 1<=options['grand_daily']<=60:
            raise CommandError('Durée comprise entre 1 et 28 jours et volume grand laboratoire entre 1 et 60 requis.')
        path=Path(options['output']).resolve()
        if not path.is_relative_to(Path('/demo/simulation-reports')) or path.exists():
            raise CommandError('Choisissez un nouveau fichier dans /demo/simulation-reports ; aucun rapport existant ne sera écrasé.')
        def progress(message):
            self.stdout.write(message)
            self.stdout.flush()
        simulation=Simulation(options['scenario'],options['seed'],options['days'],options['grand_daily'],
                              options['tiny'],progress=progress)
        report=simulation.run(isolation=not options['benchmark'])
        if options['benchmark']:
            report['scope']='benchmark-only-no-isolation-proof'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
        self.stdout.write(self.style.SUCCESS('Simulation terminée ; rapport synthétique : '+str(path)))

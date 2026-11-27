"""Export current workflow documentation without connecting to a database."""
from pathlib import Path

from django.core.management.base import BaseCommand

from api.workflow_diagrams import WORKFLOW_DOCUMENT, render_workflow


class Command(BaseCommand):
    help = 'Générer les diagrammes Mermaid des parcours métier dans docs/WORKFLOW.md.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--output', type=Path, default=WORKFLOW_DOCUMENT)

    def handle(self, *args, **options):
        destination = options['output']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_workflow(), encoding='utf-8', newline='\n')
        self.stdout.write(self.style.SUCCESS(f'Diagrammes du parcours exportés : {destination}'))

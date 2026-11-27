"""Frozen compatibility, route conformance and read-only workflow contracts."""
import ast
import io
import json
import tempfile
from itertools import product
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase

from .case_commands import HANDLERS, INSPECTION_PERMITTED, _execute
from .case_serializers import CourierPrescriptionSerializer, PrescriptionSerializer
from .domain import MANUFACTURING, REWORK_ORIGINS, ROLE_STAGES
from .models import Prescription
from .planning import EXTERNAL
from .workflow import LABELS, next_status, workflow_steps
from .workflow_diagrams import WORKFLOW_DOCUMENT, render_workflow
from .workflow_spec import (
    Action, STAGES, STEPS, StepKind, derived_external, derived_manufacturing,
    derived_rework_origins, derived_role_stages, describe_current_step,
    describe_rework_options, describe_stages, inspection_permitted,
    rework_restart_options,
)

CONTRACT = json.loads((Path(__file__).parent / 'testdata' / 'workflow_contract.json').read_text(encoding='utf-8'))


class WorkflowSpecTests(SimpleTestCase):
    def order(self, **changes):
        return Prescription(**{
            'patient_ref': 'SPEC-ONLY', 'dentist_name': 'Synthetic dentist',
            'tooth_number': 11, 'shade': 'A1', 'material': 'E-Max',
            'impression_type': 'PHYSIQUE', 'production_method': 'CFAO',
            'thermal_treatment': 'AUCUN', **changes,
        })

    def test_spec_covers_all_statuses_and_preserves_guard_constants(self):
        self.assertEqual(set(STEPS), set(Prescription.Status.values))
        self.assertEqual({key: step.label for key, step in STEPS.items()}, LABELS)
        self.assertEqual(derived_role_stages(), ROLE_STAGES)
        self.assertEqual(derived_rework_origins(), REWORK_ORIGINS)
        self.assertEqual(derived_manufacturing(), MANUFACTURING)
        self.assertEqual(derived_external(), EXTERNAL)
        stage_keys = [key for key, _ in STAGES]
        self.assertEqual(len(stage_keys), len(set(stage_keys)))
        for key, step in STEPS.items():
            with self.subTest(status=key):
                self.assertEqual(step.key, key)
                self.assertIn(step.stage, stage_keys)
                if step.kind == StepKind.INSPECT:
                    self.assertTrue(step.inspection_stages)
                if step.kind == StepKind.CONFIRM:
                    self.assertIn(step.confirm_field, {'analysis_validated', 'reception_validated'})

    def test_derived_rules_match_the_independent_pre_refactor_snapshot(self):
        # Captured from the literal guards before their Phase 6 consolidation.
        # Never regenerate this fixture from the implementation under test.
        actual = {'MANUFACTURING': MANUFACTURING, 'REWORK_ORIGINS': REWORK_ORIGINS,
                  'ROLE_STAGES': ROLE_STAGES, 'EXTERNAL': EXTERNAL, 'LABELS': LABELS,
                  'INSPECTION_PERMITTED': INSPECTION_PERMITTED}
        for name, value in actual.items():
            with self.subTest(constant=name):
                self.assertEqual(json.loads(json.dumps(value, default=sorted)), CONTRACT[name])
        self.assertEqual(INSPECTION_PERMITTED, inspection_permitted())

    def test_all_route_combinations_have_known_owned_steps(self):
        combinations = list(product(('PHYSIQUE', 'NUMERIQUE'),
                                    ('CFAO', 'IMPRESSION_3D', 'CONVENTIONNEL'),
                                    (False, True), ('AUCUN', 'FRITTAGE')))
        self.assertEqual(len(combinations), 24)
        for track, method, review, treatment in combinations:
            order = self.order(impression_type=track, production_method=method,
                               design_validation_requested=review, thermal_treatment=treatment)
            for item in workflow_steps(order):
                with self.subTest(route=(track, method, review, treatment), step=item['key']):
                    self.assertIn(item['key'], STEPS)
                    step = STEPS[item['key']]
                    if not step.external and step.kind != StepKind.CLINIC:
                        self.assertTrue(step.owner_roles)

    def test_action_spellings_and_command_defaults_preserve_wire_values(self):
        self.assertEqual(sorted(Action), sorted([*CONTRACT['ACTIONS'], 'RECORD_PAYMENT', 'REVERSE_PAYMENT']))
        for value in CONTRACT['ACTIONS']:
            with self.subTest(action=value):
                self.assertEqual(Action(value), value)
                self.assertEqual(json.dumps({'action': Action(value)}), json.dumps({'action': value}))
        for command in CONTRACT['COMMANDS'] + CONTRACT['PLANNING_COMMANDS']:
            self.assertEqual(Action(command.upper()), command.upper())

    def test_every_registered_command_has_explicit_test_source_coverage(self):
        self.assertEqual(sorted(HANDLERS), CONTRACT['COMMANDS'])
        # Exclude this module and fixtures: listing a command in the registry
        # contract itself is not evidence that another test exercises it.
        sources = [*Path(__file__).parent.glob('test*.py'),
                   Path(__file__).parents[1] / 'customers' / 'tests.py']
        strings = {node.value for source in sources if source.resolve() != Path(__file__).resolve()
                   for node in ast.walk(ast.parse(source.read_text(encoding='utf-8')))
                   if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        intentionally_untested = {}  # No registered commands are exempt.
        self.assertEqual(set(HANDLERS) - strings, set(intentionally_untested))
        self.assertFalse(set(CONTRACT['PLANNING_COMMANDS']) - strings)
        self.assertTrue(all(intentionally_untested.values()))

    def test_dispatch_preserves_validation_order_and_special_role_errors(self):
        from .signals import prescription_audit_context
        examples = [
            ('accept', 'CAO', {}, 'Your role cannot perform this command.'),
            ('accept', 'MANAGER', {}, 'Only an unaccepted new request can be accepted and advanced.'),
            ('inspection', 'MANAGER', {'advance': 'true'}, 'Inspection advance must be a boolean.'),
            ('inspection', 'MANAGER', {}, 'Supply every required check for a valid inspection stage.'),
            ('rework', 'MANAGER', {}, 'This case is not at a rework-capable step.'),
            ('design-decision', 'MANAGER', {}, 'Only the owning dentist can approve or request design changes.'),
            ('issue-pin', 'MANAGER', {}, 'Only the owning dentist can issue a delivery PIN before receipt.'),
            ('fitting', 'MANAGER', {}, 'The owning dentist records fitting after delivery.'),
            ('pause', 'MANAGER', {}, 'Provide paused=true/false and a pause reason.'),
            ('unknown', 'MANAGER', {}, 'Unknown workflow command.'),
        ]
        for command, role, data, message in examples:
            with self.subTest(command=command, role=role):
                order = self.order(accepted=True, status='DEMANDE_RECUE')
                with prescription_audit_context('test', '', {'role': role}), self.assertRaises(ValidationError) as error:
                    _execute(order, command, data, 'test', role, {})
                self.assertEqual(error.exception.messages, [message])

    def test_planning_prefix_retains_dispatch_and_shared_audit_context(self):
        from .signals import _workflow_metadata, prescription_audit_context
        order = self.order()
        with prescription_audit_context('test', '', {'role': 'MANAGER'}):
            metadata = _workflow_metadata.get()
            with patch('api.planning.task_command', return_value={'planning': True}) as command:
                self.assertEqual(_execute(order, 'planning-unknown', {}, 'test', 'MANAGER', {}), {'planning': True})
                command.assert_called_once_with(order, 'planning-unknown', {}, 'test', 'MANAGER')
            with patch.dict(HANDLERS, {'context-test': (lambda *args: args[-1] is metadata, None)}):
                self.assertIs(_execute(order, 'context-test', {}, 'test', 'MANAGER', {}), True)

    def test_committed_workflow_diagrams_are_current(self):
        self.assertTrue(WORKFLOW_DOCUMENT.is_file(), f'Missing committed document: {WORKFLOW_DOCUMENT}')
        self.assertEqual(WORKFLOW_DOCUMENT.read_text(encoding='utf-8'), render_workflow(),
                         'Run manage.py export_workflow and include docs/WORKFLOW.md.')
        self.assertEqual(render_workflow().count('flowchart TD'), 6)
        self.assertIn('RETOUR_DEMANDE -. ', render_workflow())
        self.assertIn('VALIDATION_CAO -. ', render_workflow())
        self.assertIn('A_REFAIRE -. ', render_workflow())

    def test_export_command_writes_deterministically_without_database_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'nested' / 'WORKFLOW.md'
            for _ in range(2):
                call_command('export_workflow', output=destination, stdout=io.StringIO())
                self.assertEqual(destination.read_text(encoding='utf-8'), render_workflow())

    def test_descriptors_follow_each_existing_route_and_treatment_label(self):
        for track, method, design, treatment in product(
                ['PHYSIQUE', 'NUMERIQUE'], ['CFAO', 'IMPRESSION_3D', 'CONVENTIONNEL'],
                [False, True], ['AUCUN', 'CRISTALLISATION']):
            order = self.order(impression_type=track, production_method=method,
                               design_validation_requested=design, thermal_treatment=treatment)
            route = workflow_steps(order)
            for item in route:
                with self.subTest(track=track, method=method, design=design,
                                  treatment=treatment, status=item['key']):
                    order.status = item['key']
                    descriptor = describe_current_step(order)
                    self.assertEqual(descriptor['key'], order.status)
                    self.assertEqual(descriptor['label'], item['label'])
                    self.assertEqual(descriptor['next_key'], next_status(order))
                    self.assertEqual(descriptor['next_label'], next(
                        (row['label'] for row in route if row['key'] == next_status(order)), None))
                    stages = describe_stages(order)
                    self.assertEqual([stage['key'] for stage in stages if stage['state'] == 'current'],
                                     [STEPS[order.status].stage])
                    self.assertEqual({row['key'] for stage in stages for row in stage['steps']},
                                     {row['key'] for row in route})
            thermal = self.order(status='TRAITEMENT_THERMIQUE', thermal_treatment='CRISTALLISATION')
            self.assertEqual(describe_current_step(thermal)['label'], 'Cristallisation')

    def test_inspection_descriptor_selects_the_cases_track(self):
        for track, stage in [('PHYSIQUE', 'PHYSICAL'), ('NUMERIQUE', 'DIGITAL')]:
            for status in ['A_CONFIRMER', 'CONTROLE_DOSSIER']:
                with self.subTest(track=track, status=status):
                    order = self.order(status=status, impression_type=track)
                    self.assertEqual(describe_current_step(order)['inspection_stages'], [stage])
        self.assertEqual(describe_current_step(self.order(status='CONTROLE_MODELE'))['inspection_stages'], ['MODEL'])
        self.assertEqual(describe_current_step(self.order(status='CONTROLE_QUALITE'))['inspection_stages'], ['QUALITY'])

    def test_rework_choices_preserve_the_existing_restart_sets(self):
        for track, method in product(['PHYSIQUE', 'NUMERIQUE'],
                                     ['CFAO', 'IMPRESSION_3D', 'CONVENTIONNEL', '']):
            expected = {'SALLE_CAO', 'FINITION'} | {
                {'CFAO': 'PREPARATION_CNC', 'IMPRESSION_3D': 'PREPARATION_3D',
                 'CONVENTIONNEL': 'MODELAGE', '': 'COULEE_PLATRE'}[method]}
            if track == 'PHYSIQUE':
                expected |= {'COULEE_PLATRE', 'SCAN_LABO'}
            for status in REWORK_ORIGINS:
                with self.subTest(track=track, method=method, status=status):
                    order = self.order(status=status, impression_type=track, production_method=method)
                    self.assertEqual(rework_restart_options(order), expected)
                    self.assertEqual(describe_rework_options(order), [
                        {'key': key, 'label': LABELS[key]} for key in sorted(expected)])
        for status in set(STEPS) - REWORK_ORIGINS:
            self.assertEqual(describe_rework_options(self.order(status=status)), [])

    def test_rework_stage_does_not_mark_a_future_restart_stage_done(self):
        order = self.order(status='A_REFAIRE', rework_restart_status='SALLE_CAO')
        stages = {stage['key']: stage for stage in describe_stages(order)}
        self.assertEqual(stages['FABRICATION']['state'], 'current')
        self.assertEqual(stages['CONCEPTION']['state'], 'todo')
        self.assertEqual(stages['MODELE']['state'], 'done')
        self.assertEqual(describe_current_step(order)['next_key'], 'SALLE_CAO')

    def test_legacy_and_terminal_descriptors_preserve_the_existing_routes(self):
        order = self.order(status='FRITTAGE_9H', intake_version=1)
        route_keys = {row['key'] for row in workflow_steps(order)}
        self.assertIn('FRITTAGE_9H', route_keys)
        self.assertNotIn('COULEE_PLATRE', route_keys)
        self.assertNotIn('CLOTURE', {stage['key'] for stage in describe_stages(order)})
        self.assertEqual(describe_current_step(order)['label'], LABELS['FRITTAGE_9H'])
        done = describe_current_step(self.order(status='CLOTURE'))
        self.assertEqual(done['kind'], 'DONE')
        self.assertIsNone(done['next_key'])
        self.assertIsNone(done['next_label'])
        self.assertIsNone(describe_current_step(self.order(status='UNKNOWN_LEGACY_STATUS')))

    def test_planning_destinations_are_server_derived_without_mutating_the_case(self):
        for track, method, treatment in product(['PHYSIQUE', 'NUMERIQUE'],
                ['CFAO', 'IMPRESSION_3D', 'CONVENTIONNEL'], ['AUCUN', 'FRITTAGE']):
            order = self.order(status='PLANIFICATION', impression_type=track, production_method='', thermal_treatment=treatment)
            destination = describe_current_step(order)['planning_options'][method]
            self.assertEqual(order.production_method, '')
            order.production_method = method
            self.assertEqual(destination['next_key'], next_status(order))
            self.assertEqual(destination['next_label'], LABELS[next_status(order)])

    def test_courier_labels_are_read_only_server_labels_with_restricted_fields(self):
        serializer = CourierPrescriptionSerializer()
        self.assertTrue(serializer.fields['status_label'].read_only)
        self.assertEqual(set(serializer.fields), {'id', 'patient_ref', 'dentist_name', 'status', 'status_label',
            'delivery_date', 'clinic_name', 'pickup_address', 'contact_phone', 'created_at', 'updated_at'})
        for status in STEPS:
            with self.subTest(status=status):
                data = CourierPrescriptionSerializer(self.order(status=status)).data
                self.assertEqual(data['status_label'], LABELS[status])

    def test_serializer_descriptors_are_read_only_query_free_and_viewer_independent(self):
        order = self.order(status='CONTROLE_DOSSIER')
        expected = {'current_step': describe_current_step(order), 'stages': describe_stages(order),
                    'rework_restart_options': describe_rework_options(order)}
        for role in ['MANAGER', 'RECEPTION', 'CAO', 'DENTIST']:
            serializer = PrescriptionSerializer(context={'command_role': role})
            for name, value in expected.items():
                with self.subTest(role=role, field=name):
                    field = serializer.fields[name]
                    self.assertTrue(field.read_only)
                    self.assertEqual(field.to_representation(order), value)
        self.assertEqual(set(expected['current_step']), {
            'key', 'label', 'stage', 'stage_label', 'kind', 'owner_roles', 'external',
            'rework_origin', 'inspection_stages', 'confirm_field', 'instruction',
            'next_key', 'next_label', 'next_requires_lot',
        })

    def test_lot_requirement_is_announced_on_the_step_before_manufacturing(self):
        from .domain import MANUFACTURING
        for track, method in product(['PHYSIQUE', 'NUMERIQUE'], ['CFAO', 'IMPRESSION_3D', 'CONVENTIONNEL']):
            for step in STEPS:
                order = self.order(status=step, impression_type=track, production_method=method)
                descriptor = describe_current_step(order)
                if descriptor is None:
                    continue
                with self.subTest(track=track, method=method, step=step):
                    self.assertEqual(descriptor['next_requires_lot'], next_status(order) in MANUFACTURING)

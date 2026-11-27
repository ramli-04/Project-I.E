import unittest
from prepare_v1_operations import ensure_demo_environment, missing_items, should_archive, should_pause, STOCK


class OperationsSafetyTests(unittest.TestCase):
    def test_refused_outside_demo_container(self):
        with self.assertRaises(RuntimeError):
            ensure_demo_environment({}, container=True)
        with self.assertRaises(RuntimeError):
            ensure_demo_environment({'CABINET_SIMULATION': '1', 'POSTGRES_HOST': 'postgres', 'POSTGRES_DB': 'cabinet_demo'}, container=False)
        with self.assertRaises(RuntimeError):
            ensure_demo_environment({'CABINET_SIMULATION': '1', 'POSTGRES_HOST': 'postgres', 'POSTGRES_DB': 'cabinet_sim'}, container=True)

    def test_only_open_browser_cases_are_paused_and_protected_cases_never(self):
        self.assertTrue(should_pause({'patient_ref': 'BROWSER-abc', 'status': 'SALLE_CAO', 'is_paused': False}))
        self.assertFalse(should_pause({'patient_ref': 'BROWSER-abc', 'status': 'CLOTURE', 'is_paused': False}))
        self.assertFalse(should_pause({'patient_ref': 'BROWSER-abc', 'status': 'SALLE_CAO', 'is_paused': True}))
        for reference in ['MY-TEST-001', 'TEST-2611-01', 'V1-RETARD-1', 'DEMO-1']:
            self.assertFalse(should_pause({'patient_ref': reference, 'status': 'SALLE_CAO', 'is_paused': False}))

    def test_only_the_four_listed_old_cases_are_archived(self):
        for reference in ['DEMO-CNC-APPROVAL', 'DEMO-PRINT-EXPRESS', 'DEMO-PRINT-STANDARD', 'MY-DEMO-001']:
            self.assertTrue(should_archive({'patient_ref': reference, 'status': 'SALLE_CAO', 'is_paused': False}))
            self.assertFalse(should_archive({'patient_ref': reference, 'status': 'SALLE_CAO', 'is_paused': True}))
        for reference in ['MY-TEST-001', 'TEST-2611-01', 'V1-RETARD-1', 'DEMO-OTHER', 'BROWSER-1']:
            self.assertFalse(should_archive({'patient_ref': reference, 'status': 'SALLE_CAO', 'is_paused': False}))

    def test_stock_catalogue_is_idempotent_by_name(self):
        self.assertEqual(len(missing_items([])), len(STOCK))
        self.assertEqual(missing_items([row[0].upper() for row in STOCK]), [])


if __name__ == '__main__':
    unittest.main()

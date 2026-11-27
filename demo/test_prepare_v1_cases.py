import unittest
from prepare_v1_cases import ensure_demo_environment, assert_created_order
from prepare_v1_aging import ensure_verification


class DemoFixtureSafetyTests(unittest.TestCase):
    def test_missing_flag_is_refused_before_django_or_database_use(self):
        with self.assertRaises(RuntimeError):
            ensure_demo_environment({}, container=True)

    def test_host_execution_is_refused_even_with_demo_environment(self):
        with self.assertRaises(RuntimeError):
            ensure_demo_environment({'CABINET_SIMULATION':'1','POSTGRES_HOST':'postgres','POSTGRES_DB':'cabinet_demo'}, container=False)

    def test_only_demo_database_is_allowed_and_simulator_database_is_refused(self):
        base={'CABINET_SIMULATION':'1','POSTGRES_HOST':'postgres','POSTGRES_DB':'cabinet_demo'}
        ensure_demo_environment(base, container=True)
        for key,value in [('POSTGRES_HOST','localhost'),('POSTGRES_DB','cabinet_sim')]:
            with self.assertRaises(RuntimeError):
                ensure_demo_environment({**base,key:value}, container=True)

    def test_only_exact_new_v1_reference_is_accepted(self):
        assert_created_order({'patient_ref':'V1-COMMANDE-test'},'V1-COMMANDE-test')
        for actual,expected in [('MY-TEST-001','V1-COMMANDE-test'),('MY-TEST-001','MY-TEST-001'),('V1-other','V1-COMMANDE-test')]:
            with self.assertRaises(RuntimeError):
                assert_created_order({'patient_ref':actual},expected)

    def test_aging_tool_refuses_main_and_host_before_django(self):
        base={'CABINET_SIMULATION':'1','POSTGRES_HOST':'postgres','POSTGRES_DB':'cabinet_demo'}
        with self.assertRaises(RuntimeError):
            ensure_verification(base, container=True)
        with self.assertRaises(RuntimeError):
            ensure_verification({**base, 'GESTION_LABO_VERIFICATION':'1'}, container=False)
        ensure_verification({**base, 'GESTION_LABO_VERIFICATION':'1'}, container=True)


if __name__ == '__main__':
    unittest.main()

from django.core.cache import cache
from django.test import SimpleTestCase
from django_tenants.utils import schema_context


class TenantCacheKeyTests(SimpleTestCase):
    def test_identical_order_keys_are_isolated_between_schemas(self):
        keys = {}
        for schema in ("public", "labo1", "labo2"):
            with schema_context(schema):
                keys[schema] = cache.make_key("active_orders")
                self.assertTrue(keys[schema].startswith(f"{schema}:"))
        self.assertEqual(len(set(keys.values())), 3)
        with schema_context("labo1"):
            self.assertEqual(cache.make_key("active_orders"), keys["labo1"])

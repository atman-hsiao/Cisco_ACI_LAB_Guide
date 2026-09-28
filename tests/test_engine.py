import unittest

from aci_lab.apic import ObjectState
from aci_lab.engine import DeclarativeEngine


class FakeClient:
    def __init__(self, objects=None):
        self.objects = objects or {}
        self.writes = []

    def get_object(self, dn):
        return ObjectState(dn in self.objects, self.objects.get(dn, {}))

    def upsert(self, class_name, dn, attributes):
        self.writes.append(("upsert", class_name, dn, attributes))
        self.objects[dn] = dict(attributes)

    def delete(self, class_name, dn):
        self.writes.append(("delete", class_name, dn))
        self.objects.pop(dn, None)


class EngineTests(unittest.TestCase):
    chapter = {"chapter": 8, "objects": [{"class": "fvTenant", "dn": "uni/tn-TN_POC", "attributes": {"name": "TN_POC"}}]}

    def test_create_missing_object(self):
        client = FakeClient()
        result = DeclarativeEngine(client).apply_chapter(self.chapter)
        self.assertEqual(result[0].action, "CREATE")
        self.assertEqual(len(client.writes), 1)

    def test_update_only_managed_fields(self):
        client = FakeClient({"uni/tn-TN_POC": {"name": "WRONG", "extra": "preserve"}})
        DeclarativeEngine(client).apply_chapter(self.chapter)
        self.assertEqual(client.objects["uni/tn-TN_POC"]["name"], "TN_POC")

    def test_dry_run_has_no_writes(self):
        client = FakeClient()
        changes = DeclarativeEngine(client, dry_run=True).apply_chapter(self.chapter)
        self.assertEqual(changes[0].action, "CREATE")
        self.assertFalse(client.writes)


if __name__ == "__main__":
    unittest.main()

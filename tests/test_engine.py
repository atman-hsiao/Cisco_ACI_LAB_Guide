import unittest
from unittest.mock import patch

from aci_lab.apic import ObjectState
from aci_lab.engine import DeclarativeEngine
from aci_lab import cli


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
    def test_status_color_can_be_enabled_and_disabled(self):
        with patch.object(cli, "COLOR_ENABLED", True):
            self.assertEqual(cli.styled("MATCHED", "green"), "\033[32mMATCHED\033[0m")
        with patch.object(cli, "COLOR_ENABLED", False):
            self.assertEqual(cli.styled("MATCHED", "green"), "MATCHED")

    def test_warning_is_red_when_color_is_enabled(self):
        with patch.object(cli, "COLOR_ENABLED", True):
            self.assertEqual(cli.warning("警告"), "\033[91m警告\033[0m")

    def test_no_color_option_disables_color(self):
        self.assertFalse(cli.configure_color(True))

    def test_redirected_output_disables_color(self):
        with patch.object(cli.sys.stdout, "isatty", return_value=False):
            self.assertFalse(cli.configure_color(False))

    def test_matching_object_is_reported_as_matched(self):
        client = FakeClient({"uni/test": {"name": "test"}})
        engine = DeclarativeEngine(client)
        result = engine.inspect_chapter({
            "chapter": 4,
            "objects": [{"class": "testClass", "dn": "uni/test", "attributes": {"name": "test"}}],
        })
        self.assertEqual(result[0].action, "MATCHED")

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

    def test_apply_deletes_only_matching_obsolete_object(self):
        client = FakeClient({
            "uni/current": {"name": "CURRENT"},
            "uni/old": {"name": "OLD", "descr": "Cisco ACI LAB Guide"},
            "uni/user": {"name": "USER", "descr": "owned elsewhere"},
        })
        chapter = {
            "chapter": 6,
            "objects": [{"class": "testClass", "dn": "uni/current", "attributes": {"name": "CURRENT"}}],
            "obsolete_objects": [
                {"class": "testClass", "dn": "uni/old", "match_attributes": {"name": "OLD", "descr": "Cisco ACI LAB Guide"}},
                {"class": "testClass", "dn": "uni/user", "match_attributes": {"name": "USER", "descr": "Cisco ACI LAB Guide"}},
            ],
        }
        result = DeclarativeEngine(client).apply_chapter(chapter)
        self.assertIn("uni/old", [item.dn for item in result if item.action == "DELETE"])
        self.assertNotIn("uni/old", client.objects)
        self.assertIn("uni/user", client.objects)

    def test_cleanup_deletes_matching_obsolete_object(self):
        client = FakeClient({"uni/old": {"name": "OLD", "descr": "Cisco ACI LAB Guide"}})
        chapter = {
            "chapter": 6,
            "objects": [],
            "obsolete_objects": [
                {"class": "testClass", "dn": "uni/old", "match_attributes": {"name": "OLD", "descr": "Cisco ACI LAB Guide"}},
            ],
        }
        result = DeclarativeEngine(client).cleanup_chapters([chapter])
        self.assertEqual(result[0].action, "DELETE")
        self.assertNotIn("uni/old", client.objects)


if __name__ == "__main__":
    unittest.main()

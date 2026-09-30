import unittest
from pathlib import Path

import yaml


class ChapterFourConfigTests(unittest.TestCase):
    def test_oob_contract_has_provider_and_consumer(self):
        path = Path(__file__).resolve().parents[1] / "config" / "chapters" / "chapter_04_fabric_registration.yml"
        chapter = yaml.safe_load(path.read_text(encoding="utf-8"))
        by_class = {}
        for obj in chapter["objects"]:
            by_class.setdefault(obj["class"], []).append(obj)

        self.assertEqual(by_class["vzOOBBrCP"][0]["dn"], "uni/tn-mgmt/oobbrc-oob-default")
        self.assertEqual(
            by_class["mgmtRsOoBProv"][0]["attributes"]["tnVzOOBBrCPName"],
            "oob-default",
        )
        self.assertEqual(
            by_class["mgmtRsOoBCons"][0]["attributes"]["tnVzOOBBrCPName"],
            "oob-default",
        )


class ChapterSixConfigTests(unittest.TestCase):
    def load_chapter(self):
        path = Path(__file__).resolve().parents[1] / "config" / "chapters" / "chapter_06_domains_aaep.yml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_physical_domains_do_not_send_unsupported_description(self):
        chapter = self.load_chapter()
        domains = [obj for obj in chapter["objects"] if obj["class"] == "physDomP"]

        self.assertEqual(len(domains), 3)
        self.assertTrue(all(set(obj["attributes"]) == {"name"} for obj in domains))

    def test_static_vlan_pool_names_include_allocation_suffix(self):
        chapter = self.load_chapter()
        pools = [obj for obj in chapter["objects"] if obj["class"] == "fvnsVlanInstP"]
        self.assertEqual(
            {obj["attributes"]["name"] for obj in pools},
            {"VLAN_WEB_STATIC", "VLAN_AP_STATIC", "VLAN_DB_STATIC"},
        )


if __name__ == "__main__":
    unittest.main()

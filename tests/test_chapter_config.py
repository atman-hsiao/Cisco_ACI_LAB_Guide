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


if __name__ == "__main__":
    unittest.main()

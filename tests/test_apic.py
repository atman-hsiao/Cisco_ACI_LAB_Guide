import unittest

from aci_lab.apic import ApicClient


class ClusterClient(ApicClient):
    def __init__(self, rows):
        self.rows = rows

    def query_class(self, class_name):
        self.asserted_class = class_name
        return self.rows


class ApicClusterTests(unittest.TestCase):
    def test_cluster_views_are_deduplicated(self):
        rows = []
        for _view in range(3):
            for controller_id in (1, 2, 3):
                rows.append({"id": str(controller_id), "health": "fully-fit", "operSt": "available"})
        fully_fit, quorum, controllers = ClusterClient(rows).cluster_health()
        self.assertTrue(fully_fit)
        self.assertTrue(quorum)
        self.assertEqual([row["id"] for row in controllers], ["1", "2", "3"])

    def test_no_quorum_when_only_one_controller_is_active(self):
        rows = [
            {"id": "1", "health": "fully-fit", "operSt": "available"},
            {"id": "2", "health": "unfit", "operSt": "unavailable"},
            {"id": "3", "health": "unfit", "operSt": "inactive"},
        ]
        fully_fit, quorum, _ = ClusterClient(rows).cluster_health()
        self.assertFalse(fully_fit)
        self.assertFalse(quorum)


class InventoryClient(ApicClient):
    def __init__(self, rows_by_class):
        self.rows_by_class = rows_by_class

    def query_class(self, class_name):
        return self.rows_by_class.get(class_name, [])


class SwitchInventoryTests(unittest.TestCase):
    def test_available_serials_include_loose_and_registered_nodes(self):
        client = InventoryClient({
            "fabricLooseNode": [{"serial": "LOOSE1"}],
            "fabricNode": [{"serial": "REGISTERED1"}, {"id": "201"}],
        })
        self.assertEqual(client.available_switch_serials(), {"LOOSE1", "REGISTERED1"})


if __name__ == "__main__":
    unittest.main()

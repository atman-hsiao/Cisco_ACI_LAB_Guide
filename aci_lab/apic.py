from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests
import urllib3


class ApicError(RuntimeError):
    pass


@dataclass
class ObjectState:
    exists: bool
    attributes: dict[str, Any]


class ApicClient:
    def __init__(self, endpoints: list[str], username: str, password: str, verify_tls: bool, timeout: int = 30):
        self.endpoints = endpoints
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.session = requests.Session()
        self.base_url = ""
        if not verify_tls:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def login(self) -> str:
        errors = []
        for endpoint in self.endpoints:
            url = f"https://{endpoint}"
            try:
                response = self.session.post(
                    f"{url}/api/aaaLogin.json",
                    json={"aaaUser": {"attributes": {"name": self.username, "pwd": self.password}}},
                    verify=self.verify_tls,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                self._raise_for_apic_error(response.json())
                self.base_url = url
                return endpoint
            except Exception as exc:  # each endpoint contributes diagnostic context
                errors.append(f"{endpoint}: {exc}")
        raise ApicError("無法登入任何 APIC: " + " | ".join(errors))

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if not self.base_url:
            raise ApicError("尚未登入 APIC")
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            verify=self.verify_tls,
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        data = response.json() if response.content else {"imdata": []}
        self._raise_for_apic_error(data)
        return data

    @staticmethod
    def _raise_for_apic_error(data: dict[str, Any]) -> None:
        for item in data.get("imdata", []):
            if "error" in item:
                attrs = item["error"].get("attributes", {})
                raise ApicError(f"APIC {attrs.get('code', '')}: {attrs.get('text', 'unknown error')}")

    def get_object(self, dn: str) -> ObjectState:
        data = self._request("GET", f"/api/mo/{quote(dn, safe='[]/-_')}.json")
        if not data.get("imdata"):
            return ObjectState(False, {})
        wrapper = data["imdata"][0]
        body = next(iter(wrapper.values()))
        return ObjectState(True, body.get("attributes", {}))

    def upsert(self, class_name: str, dn: str, attributes: dict[str, Any]) -> None:
        attrs = {"dn": dn, **attributes}
        payload = {class_name: {"attributes": attrs}}
        self._request("POST", f"/api/mo/{quote(dn, safe='[]/-_')}.json", json=payload)

    def delete(self, class_name: str, dn: str) -> None:
        payload = {class_name: {"attributes": {"dn": dn, "status": "deleted"}}}
        self._request("POST", f"/api/mo/{quote(dn, safe='[]/-_')}.json", json=payload)

    def query_class(self, class_name: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/api/class/{class_name}.json")
        rows = []
        for item in data.get("imdata", []):
            if class_name in item:
                rows.append(item[class_name].get("attributes", {}))
        return rows

    def cluster_health(self) -> tuple[bool, bool, list[dict[str, Any]]]:
        rows = self.query_class("infraWiNode")
        controllers = [r for r in rows if str(r.get("id", "")) in {"1", "2", "3"}]
        healthy_words = {"fully-fit", "fullyFit", "available", "in-service"}
        fully_fit = len(controllers) == 3 and all(
            any(str(r.get(k, "")) in healthy_words for k in ("health", "operSt", "state"))
            for r in controllers
        )
        active = sum(1 for r in controllers if str(r.get("operSt", r.get("state", ""))) not in {"unavailable", "out-of-service", "inactive"})
        quorum = active >= 2
        return fully_fit, quorum, controllers

    def discovered_switch_serials(self) -> set[str]:
        rows = self.query_class("fabricLooseNode")
        return {str(row.get("serial") or row.get("id") or "") for row in rows if row.get("serial") or row.get("id")}

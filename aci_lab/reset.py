from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Any

import paramiko


class ResetError(RuntimeError):
    pass


@dataclass
class SshTarget:
    name: str
    host: str
    kind: str


class FabricResetter:
    """Implements Cisco's clean-initialization sequence without touching CIMC."""

    def __init__(self, inventory: dict[str, Any], username: str, password: str, dry_run: bool = False):
        self.inventory = inventory
        self.username = username
        self.password = password
        self.dry_run = dry_run

    @staticmethod
    def tcp_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def targets(self) -> list[SshTarget]:
        result = [SshTarget(a["name"], a["management_ip"], "apic") for a in self.inventory["apics"]]
        result.extend(SshTarget(s["name"], s["management_ip"], "switch") for s in self.inventory["switches"])
        return result

    def preflight(self) -> list[str]:
        errors = []
        for apic in self.inventory["apics"]:
            if not self.tcp_reachable(apic["cimc_ip"], 443):
                errors.append(f"{apic['name']} CIMC {apic['cimc_ip']}:443 無法連線")
        expected_serial = {s["management_ip"]: s["serial"] for s in self.inventory["switches"]}
        for target in self.targets():
            try:
                client = self._connect(target)
                command = "show inventory" if target.kind == "switch" else "hostname"
                _, stdout, stderr = client.exec_command(command, timeout=15)
                identity = (stdout.read() + stderr.read()).decode("utf-8", errors="replace")
                if target.kind == "switch" and expected_serial[target.host] not in identity:
                    errors.append(f"{target.name} {target.host}: 序號驗證失敗，期望 {expected_serial[target.host]}")
                if target.kind == "apic" and target.name.lower() not in identity.lower():
                    errors.append(f"{target.name} {target.host}: Hostname 身分驗證失敗")
                client.close()
            except Exception as exc:
                errors.append(f"{target.name} {target.host}: {exc}")
        return errors

    def _connect(self, target: SshTarget) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(target.host, username=self.username, password=self.password, timeout=10, banner_timeout=15)
        return client

    @staticmethod
    def _interactive(client: paramiko.SSHClient, commands: list[tuple[str, str | None]], timeout: int = 45) -> None:
        channel = client.invoke_shell()
        channel.settimeout(2)
        for command, answer in commands:
            channel.send(command + "\n")
            time.sleep(2)
            if answer:
                channel.send(answer + "\n")
                time.sleep(2)

    def execute(self) -> None:
        if self.dry_run:
            return
        # Cisco clean initialization: switches first, APICs last. CIMC is never modified.
        for target in [t for t in self.targets() if t.kind == "switch"]:
            client = self._connect(target)
            try:
                self._interactive(client, [("acidiag touch clean", "y"), ("reload", "y")])
            finally:
                client.close()
        for target in [t for t in self.targets() if t.kind == "apic"]:
            client = self._connect(target)
            try:
                self._interactive(client, [("acidiag touch clean", "y"), ("acidiag touch setup", None), ("acidiag reboot", "y")])
            finally:
                client.close()

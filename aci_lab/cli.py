from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from .apic import ApicClient, ApicError
from .config import ConfigurationError, LabConfig
from .engine import DeclarativeEngine
from .logging_utils import exception_logger
from .reset import FabricResetter


AUTOMATED_FIRST_CHAPTER = 4
AUTOMATED_LAST_CHAPTER = 11
CLEANUP_FIRST_CHAPTER = 5


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aci_lab.py", description="Cisco ACI LAB Guide 自動化工具")
    p.add_argument("command", choices=["status", "prepare", "apply", "verify", "cleanup", "reset-fabric"])
    p.add_argument("--chapter", type=int, choices=range(1, 14))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--config-root", type=Path, default=Path(__file__).resolve().parents[1])
    return p


def credentials() -> tuple[str, str]:
    username = input("帳號: ").strip()
    password = getpass.getpass("密碼: ")
    if not username or not password:
        raise RuntimeError("帳號與密碼不可空白")
    return username, password


def print_changes(changes) -> bool:
    ok = True
    for item in changes:
        print(f"Chapter {item.chapter:02d} {item.action:9s} {item.dn}")
        for key, values in item.differences.items():
            print(f"  {key}: {values[0]!r} -> {values[1]!r}")
        if item.action != "MATCHED":
            ok = False
    return ok


def confirm_cluster(client: ApicClient, write: bool) -> None:
    fully_fit, quorum, rows = client.cluster_health()
    if fully_fit:
        print("APIC Cluster: Fully Fit")
        return
    print("警告：APIC Cluster 並非 Fully Fit")
    for row in rows:
        print(f"  Controller {row.get('id', '?')}: {row.get('health', row.get('operSt', row.get('state', 'unknown')))}")
    if write and not quorum:
        raise RuntimeError("APIC Cluster 已失去 Quorum，禁止 Policy 寫入")
    if write and input("Cluster 仍有 Quorum。是否繼續？輸入 YES: ").strip() != "YES":
        raise RuntimeError("使用者取消操作")


def connected(config: LabConfig, username: str, password: str) -> ApicClient:
    mgmt = config.settings["management"]
    client = ApicClient(
        mgmt["api_endpoint_order"], username, password,
        bool(mgmt["verify_tls"]), int(mgmt["request_timeout_seconds"]),
    )
    endpoint = client.login()
    print(f"APIC Endpoint: {endpoint}")
    if not mgmt["verify_tls"]:
        print("警告：TLS 憑證驗證已關閉，只適用於隔離 LAB。")
    return client


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.config_root.resolve()
    try:
        config = LabConfig(root)
        username, password = credentials()
        if args.command == "reset-fabric":
            return reset_fabric(config, username, password, args.dry_run)
        client = connected(config, username, password)
        write = args.command in {"prepare", "apply", "cleanup"} and not args.dry_run
        confirm_cluster(client, write=write)
        engine = DeclarativeEngine(client, dry_run=args.dry_run)
        return run_policy_command(config, engine, args)
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except Exception as exc:
        logger = exception_logger(root)
        logger.exception("command=%s chapter=%s error=%s", args.command, args.chapter, exc)
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1


def run_policy_command(config: LabConfig, engine: DeclarativeEngine, args: argparse.Namespace) -> int:
    if args.command == "status":
        all_ok = True
        for chapter in config.chapter_range(AUTOMATED_FIRST_CHAPTER, AUTOMATED_LAST_CHAPTER):
            changes = engine.inspect_chapter(chapter)
            ok = all(c.action == "MATCHED" for c in changes)
            print(f"Chapter {chapter['chapter']:02d} - {chapter['name']}: {'PASS' if ok else 'INCOMPLETE'}")
            all_ok &= ok
        return 0 if all_ok else 2

    if args.command in {"prepare", "apply", "verify"} and args.chapter is None:
        raise ConfigurationError(f"{args.command} 必須指定 --chapter")

    if args.command == "prepare":
        last = min(args.chapter - 1, AUTOMATED_LAST_CHAPTER)
        if last < AUTOMATED_FIRST_CHAPTER:
            print("此前置章節為人工環境初始化，請依 Guide 操作。")
            return 0
        for chapter in config.chapter_range(AUTOMATED_FIRST_CHAPTER, last):
            if chapter["chapter"] == 4 and not engine.dry_run:
                validate_discovered_switches(config, engine.client)
            result = engine.apply_chapter(chapter)
            print_changes(result)
        print(f"環境已準備至 Chapter {args.chapter:02d} 的起始狀態。")
        return 0

    if args.command in {"apply", "verify"}:
        if args.chapter > AUTOMATED_LAST_CHAPTER:
            print("本章為人工 Ping 驗證，請依 Guide 的測試矩陣執行。")
            return 0
        if args.chapter < AUTOMATED_FIRST_CHAPTER:
            print("本章為人工 APIC/CIMC 操作，請依 Guide 執行。")
            return 0
        chapter = config.chapters[args.chapter]
        if args.command == "apply" and args.chapter == 4 and not engine.dry_run:
            validate_discovered_switches(config, engine.client)
        result = engine.apply_chapter(chapter) if args.command == "apply" else engine.inspect_chapter(chapter)
        ok = print_changes(result)
        return 0 if ok or args.command == "apply" else 2

    if args.command == "cleanup":
        first = args.chapter if args.chapter is not None else CLEANUP_FIRST_CHAPTER
        if first < CLEANUP_FIRST_CHAPTER:
            first = CLEANUP_FIRST_CHAPTER
        chapters = config.chapter_range(first, AUTOMATED_LAST_CHAPTER)
        print("將刪除下列 LAB 章節物件：" + ", ".join(str(c["chapter"]) for c in chapters))
        if not args.dry_run and input("輸入 CLEANUP 確認: ").strip() != "CLEANUP":
            raise RuntimeError("使用者取消 Cleanup")
        result = engine.cleanup_chapters(chapters)
        print_changes(result)
        return 0
    raise ConfigurationError(f"不支援命令：{args.command}")


def validate_discovered_switches(config: LabConfig, client: ApicClient) -> None:
    expected = {str(item["serial"]) for item in config.inventory["switches"]}
    discovered = client.discovered_switch_serials()
    if discovered != expected:
        missing = sorted(expected - discovered)
        unexpected = sorted(discovered - expected)
        raise RuntimeError(f"Fabric Discovery 序號不符；缺少={missing}，未預期={unexpected}")


def reset_fabric(config: LabConfig, username: str, password: str, dry_run: bool) -> int:
    resetter = FabricResetter(config.inventory, username, password, dry_run=dry_run)
    print("警告：此操作會清除 APIC Fabric/Cluster 與所有交換器 Fabric 設定，且無法復原。")
    print("CIMC 設定與 192.168.255.41-43 將被保留。")
    for target in resetter.targets():
        print(f"  {target.kind.upper():6s} {target.name:10s} {target.host}")
    if dry_run:
        print("DRY RUN：不連線、不清除、不重新啟動設備。")
        return 0
    errors = resetter.preflight()
    if errors:
        raise RuntimeError("Preflight 失敗：" + " | ".join(errors))
    expected = config.settings["safety"]["reset_confirmation"]
    if input(f"輸入完整確認字串 {expected}: ").strip() != expected:
        raise RuntimeError("確認字串不符，已取消")
    resetter.execute()
    print("重置命令已送出。請透過 CIMC KVM 依 Guide 重新初始化 APIC。")
    return 0

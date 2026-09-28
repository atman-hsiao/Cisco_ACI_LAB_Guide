# Cisco ACI LAB Guide

本專案提供 Cisco ACI 初學者 LAB Guide 與章節式自動化工具。正式內容位於 `docs/`，自動化入口為 `aci_lab.py`。

## 快速開始

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python aci_lab.py status
python aci_lab.py prepare --chapter 8 --dry-run
```

帳號與密碼只在執行時輸入，不會寫入設定檔或 Log。

## 主要命令

```text
status
prepare --chapter N
apply --chapter N
verify --chapter N
cleanup [--chapter N]
reset-fabric
```

所有會修改 ACI 的命令都支援 `--dry-run`。完整使用方式請參閱 `docs/Cisco_ACI_LAB_Guide.md`。


# Cisco ACI LAB Guide

本手冊帶領 ACI 初學者在三台 APIC、一台 Spine、兩台 Leaf 的實體 LAB 中，從環境初始化一路完成 Access Policy、Tenant、Bridge Domain、Application Profile、EPG、Contract、Static Port Binding 與 VM Ping 驗證。

每章先說明設定目的，再提供完整選單路徑、逐步操作、必填參數、驗證結果與對應自動化命令。建議先使用 GUI 手動完成，再執行 `verify`；若要跳過已學過的章節，可用 `prepare` 建立前置環境。

> **重要警告**：Permit All、Public Subnet Scope 與允許 `0.0.0.0/0` 存取 OOB Management 的設定只適用隔離 LAB。`reset-fabric` 會清除 Fabric，且無法復原。

## 如何閱讀本手冊

- **選單路徑**：從 APIC GUI 頂端選單開始的完整導覽路徑。
- **Field Name / Value**：必須輸入或選擇的欄位；未列出的欄位維持預設值。
- **驗證結果**：完成工作項目後應看到的狀態。
- **自動化對照**：檢查、建立或還原本章環境的命令。

| 狀態 | 意義 |
|---|---|
| `MATCHED` | 物件存在，且 LAB 管理欄位符合預期 |
| `CREATE` | 物件不存在，需要建立 |
| `UPDATE` | 物件存在，但受管理欄位需要修正 |
| `DELETE` | Cleanup 將刪除物件 |
| `PASS` | 本章全部符合預期 |
| `INCOMPLETE` | 本章仍有物件需要建立或修正 |

互動式終端中，`MATCHED`/`PASS` 為綠色、`CREATE` 為青色、`UPDATE`/`INCOMPLETE` 為黃色，警告、`DELETE` 與錯誤為紅色。可用 `--no-color` 停用顏色。

## LAB 設備

| 角色 | 名稱 | ID | 型號/版本 | OOB IP | CIMC IP | 序號 |
|---|---|---:|---|---|---|---|
| APIC | APIC1 | 1 | APIC-SERVER-L3 / 5.2(7f) | 192.168.255.1/24 | 192.168.255.41 | - |
| APIC | APIC2 | 2 | APIC-SERVER-L3 / 5.2(7f) | 192.168.255.2/24 | 192.168.255.42 | - |
| APIC | APIC3 | 3 | APIC-SERVER-L3 / 5.2(7f) | 192.168.255.3/24 | 192.168.255.43 | - |
| Spine | POC-S101 | 101 | N9K-C9336PQ / 14.2(7f) | 192.168.255.11/24 | - | SAL1938P7BJ |
| Leaf | POC-L201 | 201 | N9K-C93180YC-EX / 15.2(7f) | 192.168.255.21/24 | - | FDO223907JF |
| Leaf | POC-L202 | 202 | N9K-C93180YC-EX / 14.2(7f) | 192.168.255.22/24 | - | FDO213917EN |

所有管理 IP 的 Gateway 為 `192.168.255.254`，Pod ID 為 `1`。

## 實體接線

| A 端 | A 端介面 | B 端 | B 端介面 | 用途 |
|---|---|---|---|---|
| APIC1 | Fabric | POC-L201 | eth1/46 | APIC Fabric Link |
| APIC2 | Fabric | POC-L201 | eth1/47 | APIC Fabric Link |
| APIC3 | Fabric | POC-L201 | eth1/48 | APIC Fabric Link |
| POC-L201 | eth1/53 | POC-S101 | eth1/1 | Fabric Link |
| POC-L202 | eth1/53 | POC-S101 | eth1/2 | Fabric Link |
| POC-SRV1 vmnic2 | - | POC-L201 | eth1/1 | Static Port Uplink |
| POC-SRV1 vmnic3 | - | POC-L202 | eth1/1 | Static Port Uplink |
| POC-SRV2 vmnic2 | - | POC-L201 | eth1/2 | Static Port Uplink |
| POC-SRV2 vmnic3 | - | POC-L202 | eth1/2 | Static Port Uplink |

Leaf `eth1/3-4` 與 ESXi `vmnic4-5` 保留給未來 VMM LAB，本版不可配置。

## Tenant 邏輯設計

| EPG | Bridge Domain | Gateway | VLAN | Contract 角色 |
|---|---|---|---:|---|
| EPG_WEB | BD_WEB | 10.1.0.254/24 | 2101 | Consumer of `web_app` |
| EPG_AP | BD_AP | 10.2.0.254/24 | 2201 | Provider of `web_app`; Consumer of `app_db` |
| EPG_DB | BD_DB | 10.3.0.254/24 | 2301 | Provider of `app_db` |

三個 Bridge Domain 都屬於 `VRF_POC`，三個 EPG 都位於 `AP_POC`。

# 第 1 章 LAB 架構、接線與跳板機準備

## 本章目標

確認實體接線與管理網路，並在 Windows 10 跳板機準備 Python 虛擬環境。本章不修改 APIC。

## Task 1：核對接線

1. 依照「實體接線」表核對三台 APIC 到 POC-L201 的連線。
2. 核對兩台 Leaf 的 `eth1/53` 到 Spine 的連線。
3. 核對 POC-SRV1 的 `vmnic2/3` 到兩台 Leaf 的 `eth1/1`。
4. 核對 POC-SRV2 的 `vmnic2/3` 到兩台 Leaf 的 `eth1/2`。
5. 確認 Leaf `eth1/3-4` 沒有被納入本次 LAB。

## Task 2：確認管理網路

在 PowerShell 測試三台 CIMC：

```powershell
Test-NetConnection 192.168.255.41 -Port 443
Test-NetConnection 192.168.255.42 -Port 443
Test-NetConnection 192.168.255.43 -Port 443
```

`TcpTestSucceeded` 應為 `True`。若 APIC 已初始化，再測試 `192.168.255.1-3` 的 TCP 443。

## Task 3：準備 Python

1. 進入專案根目錄。

```powershell
cd C:\Users\POC\Desktop\ACILAB\Cisco_ACI_LAB_Guide
```

2. 建立並啟用虛擬環境。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

3. 確認 Python 路徑。

```powershell
python -c "import sys; print(sys.executable)"
```

預期路徑結尾為 `.venv\Scripts\python.exe`。

## 本章驗證

```powershell
python .\aci_lab.py --help
```

應看到 `status`、`prepare`、`apply`、`verify`、`cleanup`、`reset-fabric`。

# 第 2 章 完整環境重置

## 本章目標

將交換器清回可探索狀態，並將 APIC 清回 Setup Utility 狀態。CIMC 不會被重置。

> **破壞性操作**：若只要重做 Access Policy 或 Tenant，請使用第 13 章的 `cleanup`。

## Task 1：預覽

```powershell
python .\aci_lab.py reset-fabric --dry-run
```

1. 核對目標是否為 APIC1-3、POC-S101、POC-L201、POC-L202。
2. 確認畫面顯示 `DRY RUN`；此模式不連線、不清除、不重新啟動。

## Task 2：正式重置

1. 確認三台 CIMC KVM 可用，並記錄第 3 章參數。
2. 執行：

```powershell
python .\aci_lab.py reset-fabric
```

3. 輸入共用管理帳號與密碼。
4. 等待 Preflight 檢查 CIMC、SSH、交換器序號與 APIC Hostname。
5. 只有確定要清除時，完整輸入：

```text
RESET TN_POC FABRIC
```

## 本章驗證

1. CIMC 仍可用原 IP 登入。
2. APIC 開機後顯示 Setup Utility。
3. Spine/Leaf 不再保留舊 Fabric Policy，可重新探索。

# 第 3 章 APIC Setup Utility 與 Cluster 建立

## 本章目標

透過 CIMC KVM 初始化三台 APIC，使三個 Controller 加入同一 Fabric 並達到 Fully Fit。

## Task 1：初始化 APIC1

1. 登入 `https://192.168.255.41`，開啟 KVM Console。
2. 在 Setup Utility 選擇建立新 Fabric。
3. 輸入下表；未列出的欄位維持預設值。

| Field Name | Value |
|---|---|
| Fabric Name | 接受現場預設值；三台必須相同 |
| Fabric ID | Default |
| Number of Controllers | 3 |
| Controller ID | 1 |
| Controller Name | APIC1 |
| TEP Address Pool | 接受現場預設值；三台必須相同 |
| Infrastructure VLAN ID | 3967 |
| OOB Management IP | 192.168.255.1/24 |
| OOB Default Gateway | 192.168.255.254 |

4. 完成 Setup，等待 APIC1 服務啟動。

## Task 2：初始化 APIC2 與 APIC3

分別登入 CIMC `.42` 與 `.43`，使用與 APIC1 完全相同的 Fabric Name、TEP Pool、Infrastructure VLAN 與 Cluster Size：

| APIC | Controller ID | Controller Name | OOB Management IP | Gateway |
|---|---:|---|---|---|
| APIC2 | 2 | APIC2 | 192.168.255.2/24 | 192.168.255.254 |
| APIC3 | 3 | APIC3 | 192.168.255.3/24 | 192.168.255.254 |

## 本章驗證

1. 登入 `https://192.168.255.1`。
2. 前往 **System > Controllers**。
3. 確認 Controller 1、2、3 都是 `Fully Fit`。
4. 執行：

```powershell
python .\aci_lab.py status
```

畫面應顯示 `APIC Cluster: Fully Fit`；第 4～11 章為 `INCOMPLETE` 是正常結果。

# 第 4 章 Fabric Discovery、Node Registration 與 OOB Management

## 本章目標

註冊 Spine/Leaf，設定交換器 OOB IP，並建立完整的 OOB Contract Provider/Consumer 關係。

## Task 1：確認 Discovery 並註冊節點

1. 前往 **Fabric > Inventory > Fabric Membership**。
2. 依序號找到待註冊設備；不要只依暫時名稱判斷。
3. 按 **Register**，輸入：

| Serial Number | Pod ID | Node ID | Node Name | Node Type |
|---|---:|---:|---|---|
| SAL1938P7BJ | 1 | 101 | POC-S101 | Spine |
| FDO223907JF | 1 | 201 | POC-L201 | Leaf |
| FDO213917EN | 1 | 202 | POC-L202 | Leaf |

4. 每註冊一台都按 **Refresh**，等待狀態成為 `Active`。

## Task 2：設定交換器 Static OOB Address

1. 前往 **Tenants > mgmt > Node Management Addresses > Static Node Management Addresses**。
2. 建立三筆 Out-of-Band Static Node Management Address：

| Node ID | IPv4 Address | IPv4 Gateway | Management EPG |
|---:|---|---|---|
| 101 | 192.168.255.11/24 | 192.168.255.254 | default Out-of-Band EPG |
| 201 | 192.168.255.21/24 | 192.168.255.254 | default Out-of-Band EPG |
| 202 | 192.168.255.22/24 | 192.168.255.254 | default Out-of-Band EPG |

3. 儲存設定。

## Task 3：建立 OOB Contract

1. 在 `mgmt` Tenant 展開 **Contracts**，建立 Out-of-Band Contract。
2. 輸入：

| Field Name | Value |
|---|---|
| Name | oob-default |
| Description | Cisco ACI LAB Guide |

3. 在 Contract 下建立 Subject：

| Field Name | Value |
|---|---|
| Name | oob-default |
| Filter | default |

## Task 4：設定 Provider 與 Consumer

1. 前往 **Tenants > mgmt > Node Management EPGs**。
2. 選取 **Out-of-Band EPG-default**，在 Provided Contracts 加入 `oob-default`。
3. 前往 **External Management Network Instance Profiles**。
4. 建立：

| Field Name | Value |
|---|---|
| Name | LAB_OOB |
| Description | Cisco ACI LAB Guide |
| External Management Network | 0.0.0.0/0 |
| Consumed Contract | oob-default |

5. 儲存後確認沒有 `Could not resolve the target` 警告。

## 本章驗證

1. Fabric Membership 的三台交換器均為 `Active`。
2. Out-of-Band EPG `default` 提供 `oob-default`。
3. `LAB_OOB` 使用 `oob-default`。
4. 從跳板機測試三台交換器 TCP 22。
5. 執行：

```powershell
python .\aci_lab.py verify --chapter 4
```

所有項目應為 `MATCHED`。

## 自動化對照

```powershell
python .\aci_lab.py apply --chapter 4 --dry-run
python .\aci_lab.py apply --chapter 4
python .\aci_lab.py verify --chapter 4
```

一般 `cleanup` 保留第 4 章；只有 `reset-fabric` 會清除 Fabric 基礎設定。

# 第 5 章 Access Interface Policies

## 本章目標

建立可重複使用的 1G Link Level、CDP、LLDP Policy。本章只定義 Policy，尚未部署到 Port。

## Task 1：Link Level Policy

1. 前往 **Fabric > Access Policies > Policies > Interface > Leaf Interfaces > Link Level**。
2. 建立 Policy：

| Field Name | Value |
|---|---|
| Name | IntPol-1G-Auto |
| Description | Cisco ACI LAB Guide |
| Speed | 1 Gbps |
| Auto Negotiation | On |

3. 按 **Submit**。

## Task 2：CDP Policy

1. 前往 **Policies > Interface > Leaf Interfaces > CDP Interface**。
2. 建立：

| Field Name | Value |
|---|---|
| Name | IntPol-CDP-Enable |
| Description | Cisco ACI LAB Guide |
| Admin State | Enabled |

## Task 3：LLDP Policy

1. 前往 **Policies > Interface > Leaf Interfaces > LLDP Interface**。
2. 建立：

| Field Name | Value |
|---|---|
| Name | IntPol-LLDP-Enable |
| Description | Cisco ACI LAB Guide |
| Receive State | Enabled |
| Transmit State | Enabled |

## 本章驗證與自動化

```powershell
python .\aci_lab.py apply --chapter 5 --dry-run
python .\aci_lab.py apply --chapter 5
python .\aci_lab.py verify --chapter 5
```

預期三個 Policy 都顯示 `MATCHED`。

# 第 6 章 VLAN Pools、Physical Domains 與 AAEP

## 本章目標

建立 Static VLAN Namespace、Physical Domain 與共用 AAEP。VLAN Pool 定義 Encap；Domain 定義 EPG 的實體部署範圍；AAEP 將 Domain 與 Port Policy Group 串接。

## Task 1：建立 VLAN Pools

1. 前往 **Fabric > Access Policies > Pools > VLAN**。
2. 右鍵選擇 **Create VLAN Pool**。
3. 依序建立：

| Name | Allocation Mode | Range From | Range To | Block Mode |
|---|---|---:|---:|---|
| VLAN_WEB | Static Allocation | 2101 | 2110 | Static Allocation |
| VLAN_AP | Static Allocation | 2201 | 2210 | Static Allocation |
| VLAN_DB | Static Allocation | 2301 | 2310 | Static Allocation |

每個 Pool 的 Description 填入 `Cisco ACI LAB Guide`。建立 Encap Block 時先按 `+`，輸入 From/To，再按 **OK** 與 **Submit**。

## Task 2：建立 Physical Domains

1. 前往 **Physical and External Domains > Physical Domains**。
2. 建立：

| Physical Domain | VLAN Pool |
|---|---|
| DOM_PHY_WEB | VLAN_WEB |
| DOM_PHY_AP | VLAN_AP |
| DOM_PHY_DB | VLAN_DB |

APIC 5.2(7f) 的 Physical Domain (`physDomP`) 不接受 Description 屬性，因此此處不要填寫 Description。

## Task 3：建立 AAEP

1. 前往 **Global Policies > Attachable Access Entity Profiles**。
2. 建立：

| Field Name | Value |
|---|---|
| Name | AEP_PHY |
| Description | Cisco ACI LAB Guide |
| Domains | DOM_PHY_WEB, DOM_PHY_AP, DOM_PHY_DB |

3. 按 **Submit**。

## 本章驗證與自動化

```powershell
python .\aci_lab.py prepare --chapter 6
python .\aci_lab.py apply --chapter 6
python .\aci_lab.py verify --chapter 6
```

確認三個 Pool 為 Static、Domain 對應正確、`AEP_PHY` 關聯三個 Domain。

# 第 7 章 Leaf Interface Policy Group、Interface Profile 與 Switch Profile

## 本章目標

把第 5、6 章的 Policy 組成一個 Access Port Policy Group，只部署到 Leaf 201/202 的 `eth1/1-2`。四個 Port 都是獨立 Port，不建立 Port Channel 或 vPC。

## Task 1：建立 Policy Group

1. 前往 **Fabric > Access Policies > Interface Policy Groups > Leaf Access Port**。
2. 建立：

| Field Name | Value |
|---|---|
| Name | IfPolGrp-Access-Server_1G |
| Description | Cisco ACI LAB Guide |
| Link Level Policy | IntPol-1G-Auto |
| CDP Interface Policy | IntPol-CDP-Enable |
| LLDP Interface Policy | IntPol-LLDP-Enable |
| Attached Entity Profile | AEP_PHY |

3. 其他欄位維持預設值，按 **Submit**。

## Task 2：建立 Interface Profiles

1. 前往 **Interfaces > Leaf Interfaces > Profiles**。
2. 建立 `IntProf-LF201`，再建立兩個 Access Port Selector：

| Selector | Card | From Port | To Port | Policy Group |
|---|---:|---:|---:|---|
| IntSel-eth1_1 | 1 | 1 | 1 | IfPolGrp-Access-Server_1G |
| IntSel-eth1_2 | 1 | 2 | 2 | IfPolGrp-Access-Server_1G |

3. 建立 `IntProf-LF202`，使用相同兩個 Selector 與 Policy Group。

## Task 3：建立 Switch Profiles

1. 前往 **Switches > Leaf Switches > Profiles**。
2. 建立 Leaf 201 Profile：

| Field Name | Value |
|---|---|
| Name | SwProf-LF201 |
| Leaf Selector Name | Leaf201 |
| Node Block From/To | 201 / 201 |
| Associated Interface Profile | IntProf-LF201 |

3. 建立 Leaf 202 Profile：

| Field Name | Value |
|---|---|
| Name | SwProf-LF202 |
| Leaf Selector Name | Leaf202 |
| Node Block From/To | 202 / 202 |
| Associated Interface Profile | IntProf-LF202 |

## 本章驗證與自動化

1. 每台 Leaf 只關聯自己的 Interface Profile。
2. 每個 Profile 只有 `eth1/1-2`；不可包含 `eth1/3-4`。
3. 執行：

```powershell
python .\aci_lab.py prepare --chapter 7
python .\aci_lab.py apply --chapter 7
python .\aci_lab.py verify --chapter 7
```

# 第 8 章 Tenant、VRF 與 Bridge Domains

## 本章目標

建立 `TN_POC`、`VRF_POC` 與三個可路由 BD。所有 BD 啟用 Unicast Routing、ARP Flood，L2 Unknown Unicast 使用 Flood。

## Task 1：建立 Tenant 與 VRF

1. 前往 **Tenants > Add Tenant**。
2. 建立 Tenant：

| Field Name | Value |
|---|---|
| Name | TN_POC |
| Description | Cisco ACI LAB Guide |

3. 開啟 `TN_POC > Networking > VRFs`。
4. 建立 VRF：

| Field Name | Value |
|---|---|
| Name | VRF_POC |
| Description | Cisco ACI LAB Guide |

## Task 2：建立 Bridge Domains

1. 前往 **TN_POC > Networking > Bridge Domains**。
2. 建立 `BD_WEB`，在 Main/Advanced 頁面設定：

| Field Name | Value |
|---|---|
| Name | BD_WEB |
| Description | Cisco ACI LAB Guide |
| VRF | VRF_POC |
| Unicast Routing | Enabled |
| L2 Unknown Unicast | Flood |
| ARP Flooding | Enabled |

3. 在 Subnets 按 `+`，輸入 Gateway `10.1.0.254/24`，Scope 選 `Public`。
4. 以相同 Routing/Flood 設定建立：

| BD | Gateway | Scope | VRF |
|---|---|---|---|
| BD_AP | 10.2.0.254/24 | Public | VRF_POC |
| BD_DB | 10.3.0.254/24 | Public | VRF_POC |

> 本版未建立 L3Out；Public Scope 不代表 Subnet 已對外公告。

## 本章驗證與自動化

```powershell
python .\aci_lab.py prepare --chapter 8
python .\aci_lab.py apply --chapter 8
python .\aci_lab.py verify --chapter 8
```

`prepare --chapter 8` 只完成第 4～7 章，不會建立第 8 章。

# 第 9 章 Application Profile 與 EPG

## 本章目標

建立 `AP_POC` 與 WEB/AP/DB 三個 EPG，關聯正確的 BD 與 Physical Domain。本章尚不建立 Static Port。

## Task 1：建立 Application Profile

1. 前往 **Tenants > TN_POC > Application Profiles**。
2. 建立：

| Field Name | Value |
|---|---|
| Name | AP_POC |
| Description | Cisco ACI LAB Guide |

## Task 2：建立三個 EPG

1. 在 `AP_POC` 下建立 Application EPG。
2. 選擇 BD，儲存 EPG。
3. 在 EPG 下開啟 **Domains (VMs and Bare-Metals)**，加入 Physical Domain。
4. Deployment/Resolution Immediacy 都選 `Immediate`。
5. 依序建立：

| EPG | Bridge Domain | Physical Domain |
|---|---|---|
| EPG_WEB | BD_WEB | DOM_PHY_WEB |
| EPG_AP | BD_AP | DOM_PHY_AP |
| EPG_DB | BD_DB | DOM_PHY_DB |

每個 EPG 的 Description 都填入 `Cisco ACI LAB Guide`。

## 本章驗證與自動化

1. 每個 EPG 都關聯正確 BD/Domain，Static Ports 仍為空白。
2. 執行：

```powershell
python .\aci_lab.py prepare --chapter 9
python .\aci_lab.py apply --chapter 9
python .\aci_lab.py verify --chapter 9
```

# 第 10 章 Permit All Filters 與 Contracts

## 本章目標

建立 WEB 到 AP、AP 到 DB 的兩段 Contract。Consumer 發起流量，Provider 提供服務。本 LAB 使用 Permit All 方便觀察關係，正式環境不可照搬。

## Task 1：建立 WEB-to-AP Filter 與 Contract

1. 前往 **TN_POC > Contracts > Filters**。
2. 建立 Filter 與 Entry：

| Object/Field | Value |
|---|---|
| Filter Name | FLT_WEB_APP_PERMIT_ALL |
| Description | Cisco ACI LAB Guide |
| Entry Name | PERMIT_ALL |
| EtherType | Unspecified |

3. 前往 **Contracts > Standard**，建立：

| Object/Field | Value |
|---|---|
| Contract Name | web_app |
| Scope | Tenant |
| Description | Cisco ACI LAB Guide |
| Subject Name | SUBJ_WEB_APP |
| Filter | FLT_WEB_APP_PERMIT_ALL |

4. 在 `EPG_WEB > Contracts` 加入 Consumed Contract `web_app`。
5. 在 `EPG_AP > Contracts` 加入 Provided Contract `web_app`。

## Task 2：建立 APP-to-DB Filter 與 Contract

| Object/Field | Value |
|---|---|
| Filter Name | FLT_APP_DB_PERMIT_ALL |
| Entry Name / EtherType | PERMIT_ALL / Unspecified |
| Contract Name / Scope | app_db / Tenant |
| Subject Name | SUBJ_APP_DB |
| Subject Filter | FLT_APP_DB_PERMIT_ALL |

1. 在 `EPG_AP` 加入 Consumed Contract `app_db`。
2. 在 `EPG_DB` 加入 Provided Contract `app_db`。
3. 不要建立 EPG_WEB 到 EPG_DB 的直接 Contract。

## 本章驗證

| EPG | Consumed | Provided |
|---|---|---|
| EPG_WEB | web_app | - |
| EPG_AP | app_db | web_app |
| EPG_DB | - | app_db |

```powershell
python .\aci_lab.py prepare --chapter 10
python .\aci_lab.py apply --chapter 10
python .\aci_lab.py verify --chapter 10
```

# 第 11 章 Static Port Binding

## 本章目標

將三個 EPG 以 Tagged VLAN 綁定到 Leaf 201/202 的 `eth1/1-2`。介面是獨立 Switch Port，Mode 使用 Regular，不建立 vPC Path。

## 操作原理

ESXi Standard vSwitch 的兩個 Uplink 都是 Active，Port Group 負責加 VLAN Tag。因此 APIC Mode 必須為 `Regular`，不可選 Native/Untagged。

## Task 1：建立 EPG_WEB Binding

1. 前往 **TN_POC > Application Profiles > AP_POC > EPG_WEB > Static Ports**。
2. 選擇 **Deploy Static EPG on PC, VPC or Interface**。
3. 建立第一筆：

| Field Name | Value |
|---|---|
| Path Type | Port |
| Pod | pod-1 |
| Node | POC-L201 (201) |
| Path | eth1/1 |
| VLAN | 2101 |
| Deployment Immediacy | Immediate |
| Mode | Regular |

4. 再建立 Node 201 `eth1/2`、Node 202 `eth1/1`、Node 202 `eth1/2`，VLAN 都是 `2101`。

## Task 2：建立 EPG_AP 與 EPG_DB Binding

| EPG | Nodes | Interfaces | VLAN | Deployment | Mode |
|---|---|---|---:|---|---|
| EPG_AP | 201, 202 | eth1/1, eth1/2 | 2201 | Immediate | Regular |
| EPG_DB | 201, 202 | eth1/1, eth1/2 | 2301 | Immediate | Regular |

每個 EPG 各四條，共十二條。確認 Path 是 `paths-201/202`，不是 `protpaths`；不可使用 `eth1/3-4`。

## 本章驗證與自動化

```powershell
python .\aci_lab.py apply --chapter 11 --dry-run
python .\aci_lab.py apply --chapter 11
python .\aci_lab.py verify --chapter 11
```

# 第 12 章 VMware 與 VM Ping 驗證

## 本章目標

使用既有 VMware Standard vSwitch 與 VM，驗證同 EPG 跨 ESXi、Contract 跨 BD，以及沒有直接 Contract 時的隔離。本章不修改 VMware。

## 開始前確認

- POC-SRV1/2 的 `vmnic2/3` 為雙 Active Uplink。
- Load Balancing 維持 `Route based on originating virtual port ID`。
- VMware Port Group VLAN 與 EPG Encap 相同。

## Task 1：確認 VM 參數

| VM | IP/Gateway | EPG/VLAN | ESXi |
|---|---|---|---|
| POC-WEB1/3 | 10.1.0.1/3, GW .254 | EPG_WEB / 2101 | POC-SRV1 |
| POC-WEB2/4 | 10.1.0.2/4, GW .254 | EPG_WEB / 2101 | POC-SRV2 |
| POC-AP1/3 | 10.2.0.1/3, GW .254 | EPG_AP / 2201 | POC-SRV1 |
| POC-AP2/4 | 10.2.0.2/4, GW .254 | EPG_AP / 2201 | POC-SRV2 |
| POC-DB1/3 | 10.3.0.1/3, GW .254 | EPG_DB / 2301 | POC-SRV1 |
| POC-DB2/4 | 10.3.0.2/4, GW .254 | EPG_DB / 2301 | POC-SRV2 |

所有 Mask 為 `/24`，Gateway 為該網段 `.254`。

## Task 2：確認 Endpoint Learning

1. 前往各 EPG 的 **Operational > Client End-Points**。
2. 確認對應 VM 的 MAC/IP 已被學習。
3. 若未出現，檢查 VM Power、Port Group VLAN、Static Path 與 ESXi Uplink。

## Task 3：Ping 測試

| Source | Destination | 測試目的 | 預期 |
|---|---|---|---|
| POC-WEB1 | 10.1.0.2 | 同 EPG 跨 ESXi | Success |
| POC-AP1 | 10.2.0.2 | 同 EPG 跨 ESXi | Success |
| POC-DB1 | 10.3.0.2 | 同 EPG 跨 ESXi | Success |
| POC-WEB1 | 10.2.0.2 | WEB Consumer 到 AP Provider | Success |
| POC-AP1 | 10.3.0.2 | AP Consumer 到 DB Provider | Success |
| POC-WEB1 | 10.3.0.2 | 無直接 Contract | Fail |

若非預期失敗，依序檢查 OS Firewall、IP/Mask/Gateway、Port Group VLAN、Endpoint Learning、Static Path、Contract 方向。

# 第 13 章 狀態檢查、跳章準備、Cleanup 與疑難排解

## Task 1：檢查狀態

```powershell
python .\aci_lab.py status
python .\aci_lab.py verify --chapter 8
```

`status` 檢查第 4～11 章；`verify` 只檢查指定章節，兩者都不修改 APIC。

## Task 2：準備指定章節

```powershell
python .\aci_lab.py prepare --chapter 8 --dry-run
python .\aci_lab.py prepare --chapter 8
```

此命令完成第 4～7 章，但不建立第 8 章。正確物件保持不變，缺少物件建立，受管理欄位錯誤時修正，未管理欄位保留。

| Command | 結果 |
|---|---|
| `prepare --chapter 5` | 完成第 4 章 |
| `prepare --chapter 8` | 完成第 4～7 章 |
| `prepare --chapter 11` | 完成第 4～10 章 |
| `prepare --chapter 12` | 完成第 4～11 章 |

## Task 3：Cleanup

```powershell
python .\aci_lab.py cleanup --chapter 8 --dry-run
python .\aci_lab.py cleanup --chapter 8
```

正式執行時輸入 `CLEANUP`。指定章節與後續章節會反向刪除：

| Command | 刪除 | 保留 |
|---|---|---|
| `cleanup --chapter 11` | 11 | 4-10 |
| `cleanup --chapter 8` | 8-11 | 4-7 |
| `cleanup --chapter 5` | 5-11 | Chapter 4 |
| `cleanup` | 5-11 | Cluster、Registration、OOB |

即使輸入 `cleanup --chapter 4`，也會被限制為從第 5 章開始，避免清除 Fabric 基礎設定。

## Task 4：Cluster 安全機制

| Cluster 狀態 | 唯讀 | Policy 寫入 |
|---|---|---|
| Fully Fit | Allowed | Allowed |
| 有 Quorum、非 Fully Fit | Allowed | 顯示紅色警告，輸入 `YES` 才繼續 |
| 無 Quorum | Allowed | Blocked |

## Task 5：疑難排解

1. 閱讀終端紅色錯誤與 APIC Error Code。
2. 執行 `status` 確認 Endpoint 與 Cluster。
3. 使用 `--dry-run` 查看預計變更。
4. 在 APIC GUI 依 DN 找到物件。
5. 檢查 `logs` 最新檔案；工具只在異常時記錄。
6. 修正後重跑，已正確物件會被保留。

## Appendix A：命名總表

| 類別 | 物件 |
|---|---|
| Interface Policies | IntPol-1G-Auto, IntPol-CDP-Enable, IntPol-LLDP-Enable |
| VLAN Pools | VLAN_WEB, VLAN_AP, VLAN_DB |
| Physical Domains | DOM_PHY_WEB, DOM_PHY_AP, DOM_PHY_DB |
| AAEP / Policy Group | AEP_PHY / IfPolGrp-Access-Server_1G |
| Interface Profiles | IntProf-LF201, IntProf-LF202 |
| Switch Profiles | SwProf-LF201, SwProf-LF202 |
| Tenant / VRF | TN_POC / VRF_POC |
| Bridge Domains | BD_WEB, BD_AP, BD_DB |
| Application / EPG | AP_POC / EPG_WEB, EPG_AP, EPG_DB |
| Filters | FLT_WEB_APP_PERMIT_ALL, FLT_APP_DB_PERMIT_ALL |
| Contracts | web_app, app_db |

## Appendix B：常用命令

```powershell
python .\aci_lab.py status
python .\aci_lab.py verify --chapter 11
python .\aci_lab.py prepare --chapter 8 --dry-run
python .\aci_lab.py prepare --chapter 8
python .\aci_lab.py apply --chapter 11
python .\aci_lab.py cleanup --chapter 11
python .\aci_lab.py cleanup
python .\aci_lab.py reset-fabric --dry-run
```

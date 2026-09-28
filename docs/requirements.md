# Cisco ACI LAB Guide 需求規格

版本：1.0  
狀態：已確認  
日期：2026-09-28

## 目的與範圍

本專案為 ACI 初學者提供一套可重複操作的實體 LAB。內容從 Fabric 清除、APIC 三節點 Cluster、Switch Discovery、Access Policy、Tenant、VRF、Bridge Domain、Application Profile、EPG、Contract，一直到 Tagged Static Port Binding 與人工 VM Ping 驗證。

本版不包含 VMM Integration、L3Out、Internet Contract、映像版本檢查或升級、vPC、Port-Channel、LACP，以及 VMware 環境建置或自動化。

## 已確認環境

- APIC1-3：APIC-SERVER-L3，5.2(7f)，OOB `192.168.255.1-3/24`，Controller ID 1-3。
- CIMC：`192.168.255.41-43`，完整重置時必須保留。
- Spine 101：POC-S101，N9K-C9336PQ，14.2(7f)，序號 SAL1938P7BJ，OOB `192.168.255.11/24`。
- Leaf 201：POC-L201，N9K-C93180YC-EX，15.2(7f)，序號 FDO223907JF，OOB `192.168.255.21/24`。
- Leaf 202：POC-L202，N9K-C93180YC-EX，14.2(7f)，序號 FDO213917EN，OOB `192.168.255.22/24`。
- Pod：1；Infrastructure VLAN：3967；管理 Gateway：`192.168.255.254`。
- Fabric Name 與 TEP Pool 接受 Setup Utility 預設值。
- API 依 APIC1、APIC2、APIC3 順序容錯連線。

## Policy 與 Tenant 基準

- `IfPolGrp-Access-Server_1G` 只套用 Leaf 201/202 的 `eth1/1-2`。
- `eth1/3-4` 保留給未來 VMM 使用。
- Link Policy 為 `IntPol-1G-Auto`，CDP 與 LLDP 啟用。
- VLAN Pool：WEB 2101-2110、AP 2201-2210、DB 2301-2310。
- Tenant `TN_POC`、VRF `VRF_POC`、Application Profile `AP_POC`。
- WEB/AP/DB 的 Gateway 分別為 `10.1.0.254/24`、`10.2.0.254/24`、`10.3.0.254/24`。
- 所有 Subnet Scope 為 Public；BD 開啟 Unicast Routing、L2 Unknown Unicast Flood、ARP Flooding。
- 三個 EPG 分別使用 VLAN 2101、2201、2301，並綁定兩台 Leaf 的 `eth1/1-2`，Mode 為 Regular/Tagged。
- `web_app`：WEB Consumer、AP Provider；`app_db`：AP Consumer、DB Provider。
- Contract 使用各自獨立的 Permit All Filter。

## 自動化行為

- 單一入口 `python aci_lab.py`。
- 支援 `status`、`prepare`、`apply`、`verify`、`cleanup`、`reset-fabric`。
- 所有修改命令支援 `--dry-run`。
- APIC 是唯一狀態來源；不保存本機完成旗標。
- 不存在的物件自動建立；LAB 管理欄位不符時自動修正；未管理欄位不修改。
- 失敗時保留已成功設定，修正後可重跑。
- 正常執行不留 Log；Warning 或 Error 才寫入 `logs/`。
- 帳號密碼執行時輸入，密碼不得進入設定檔、命令列或 Log。
- Cluster Fully Fit 時直接執行；有 Quorum 但非 Fully Fit 時詢問；失去 Quorum 禁止 Policy 寫入。
- `reset-fabric` 可在無 Quorum 時執行，但必須完成設備與 CIMC 預檢並輸入 `RESET TN_POC FABRIC`。
- `cleanup` 刪除完整 LAB 物件及子設定，但保留 Cluster、Node Registration、OOB Management、系統 Tenant 與非 LAB 物件。

## 文件交付

- 繁體中文 Markdown、Word 與 PDF。
- 第一次出現的 ACI 物件與 GUI 選單附英文名稱。
- 以選單路徑、欄位表與文字說明為主，不依賴逐步截圖。
- 包含實體拓撲圖與 Tenant 邏輯圖。
- 每章包含學習目標、概念、GUI 步驟、驗證、自動化、清理與疑難排解。


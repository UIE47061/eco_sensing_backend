# Eco-Sensing App 差旅（travel-records）上傳機制 — 開發參考

> 目的：彙整 **App 端（Flutter 員工端）** 開發「差旅碳核算上傳」所需的 API 形狀，供實作對齊。
> 權威出處：`Eco-Sensing_專案context文件_v26.md` §4.1（規格與三軌流程）、§2/[A3]（`employee_id` 由憑證解出鐵律）；程式碼出處：`routers/eco_records.py`、`db/schema.sql`。
> 認證機制細節（登入、雙 token、401 攔截器）不重述，見 `Eco-Sensing_App_驗證機制_開發參考.md`；本文件假設 App 已持有有效 `access_token`。

---

## 0. 一句話定位

後端目前**只提供結構化資料的 CRUD 端點**（`/api/travel-records`），不做 OCR／NER／里程換算。三軌收據（高鐵電子票／計程車紙本／App 乘車截圖）的辨識與换算屬 **App 端／前處理管線**的工作（§4.1 A/B/C 三軌），App 需自行跑完 OCR → NER → 里程查詢 → 「完整記錄確認畫面」，員工確認後才把**最終結構化欄位**送進本文件描述的端點。

---

## 1. 端點總覽

| Method | 路徑 | 認證 | 用途 |
| ------ | ---- | ---- | ---- |
| `GET` | `/api/travel-records` | 不需 Bearer（現況程式碼未掛，見 §5 提醒） | 列表（分頁） |
| `POST` | `/api/travel-records` | **需 `Bearer <access_token>`** | 建立一筆差旅紀錄，`employee_id` 由 token 解出並自動寫入 |
| `GET` | `/api/travel-records/{record_id}` | 不需 Bearer | 取單筆 |
| `PATCH` | `/api/travel-records/{record_id}` | **需 `Bearer <access_token>`** | 修正既有紀錄（不改 `employee_id`） |
| `DELETE` | `/api/travel-records/{record_id}` | 不需 Bearer | 刪除 |

> 依 [A3] 全系統鐵律：**request body 絕不帶 `employee_id`**，一律由 `Authorization: Bearer` 解出（`get_current_employee` dependency）。App 端上傳流程只需呼叫 `POST /api/travel-records`；GET/PATCH/DELETE 供列表回顯與事後修正。

---

## 2. `POST /api/travel-records`

### Request Header

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request Body（對應 `TravelRecordCreate`，`routers/eco_records.py:43`）

| 欄位 | 型別 | 必填 | 說明 |
| ------ | ------ | ------ | ------ |
| `transport_mode` | string | **必填** | 交通工具代碼，如 `"mrt"`、`"hsr"`（高鐵）、`"taxi"`；對應 `EMISSION_FACTOR.key`，供後端／人工核算時查係數 |
| `travel_date` | date（`YYYY-MM-DD`） | **必填** | 出行日期 |
| `factor_id` | UUID \| null | 選填 | 對應排放係數列（`emission_factor.id`）；App 若不知道可留空，由後續人工／後端核算補上 |
| `track_type` | string \| null | 選填 | 三軌來源標記，建議值：`"hsr_ticket"`（軌 A 高鐵電子票）／`"taxi_receipt"`（軌 B 計程車紙本）／`"app_screenshot"`（軌 C App 乘車截圖）／`"manual"`；**此欄位無資料庫層 enum 限制**，命名以團隊約定為準 |
| `origin` | string \| null | 選填 | 起點（GPT-4o NER 輸出欄位之一） |
| `destination` | string \| null | 選填 | 終點 |
| `amount` | number \| null | 選填 | 票款金額（OCR 取得） |
| `distance_km` | number \| null | 選填 | 里程（TDX／Google Maps 換算結果） |
| `co2e_kg` | number \| null | 選填 | 碳排量；若 App 端已算好可直接帶入，否則留空由後端／批次核算補算 |
| `receipt_id` | string \| null | 選填 | 綁定的報銷單據 ID（§4.1「數據綁定報銷單據 ID」） |
| `status` | string | 選填，預設 `"pending"` | 紀錄狀態；目前程式碼僅有預設值，**無 enum 限制與狀態機邏輯**，App 端可依需要送 `"confirmed"` 等值，或直接不帶採預設 |

> **不得帶欄位**：`employee_id`（由 token 解出）、`id` / `created_at` / `updated_at`（資料庫自動產生）。

### Request 範例（依三軌）

```json
// 軌 A：高鐵電子票（OCR + GPT-4o NER + TDX 里程查詢後）
{
  "transport_mode": "hsr",
  "track_type": "hsr_ticket",
  "travel_date": "2026-09-14",
  "origin": "台北",
  "destination": "台中",
  "amount": 700,
  "distance_km": 165.4,
  "receipt_id": "EXP-2026-0914-01"
}
```

```json
// 軌 B：計程車紙本（OCR 取金額 + 員工手填起訖 + Google Maps 換算）
{
  "transport_mode": "taxi",
  "track_type": "taxi_receipt",
  "travel_date": "2026-09-14",
  "origin": "台北車站",
  "destination": "南港軟體園區",
  "amount": 320,
  "distance_km": 8.2,
  "receipt_id": "EXP-2026-0914-02"
}
```

```json
// 軌 C：App 乘車截圖（OCR 取起訖/距離 + GPT-4o 辨識工具 + Google Maps 補算）
{
  "transport_mode": "uber",
  "track_type": "app_screenshot",
  "travel_date": "2026-09-14",
  "origin": "信義區",
  "destination": "內湖科技園區",
  "distance_km": 6.5,
  "receipt_id": "EXP-2026-0914-03"
}
```

### Response 201（`return=representation`，PostgREST 回寫入後全列）

```json
{
  "id": "b3e2c1a0-....-....-....-............",
  "employee_id": "3f1a9c22-....-....-....-............",
  "factor_id": null,
  "track_type": "hsr_ticket",
  "transport_mode": "hsr",
  "origin": "台北",
  "destination": "台中",
  "travel_date": "2026-09-14",
  "amount": 700,
  "distance_km": 165.4,
  "co2e_kg": null,
  "receipt_id": "EXP-2026-0914-01",
  "status": "pending",
  "created_at": "2026-09-14T09:12:33.201+00:00",
  "updated_at": "2026-09-14T09:12:33.201+00:00"
}
```

### 錯誤情況

| 狀況 | 回應 |
| ------ | ------ |
| 缺 `Authorization` header | `401 { "detail": "Missing bearer token" }` |
| Access token 過期 | `401 { "detail": "Access token expired" }`（帶 `WWW-Authenticate: Bearer`）→ 走 401 攔截器換發＋重放（見驗證機制文件 §3.4） |
| Access token 無效／格式錯 | `401 { "detail": "Invalid access token" }` |
| 缺必填欄位（`transport_mode` / `travel_date`）或型別錯 | `422`（FastAPI/Pydantic 自動驗證，標準錯誤格式） |

---

## 3. `PATCH /api/travel-records/{record_id}`（修正既有紀錄）

- Header 同上需 `Bearer`；欄位皆選填（對應 `TravelRecordUpdate`，僅送要改的欄位）。
- **不接受、也不應送 `employee_id`**（body 內即使帶了也不會被用來變更歸戶，`update_record` 直接把 payload 原樣 PATCH 進去，仍建議 App 端不帶以維持鐵律一致）。
- 全部欄位皆為 `None` / 不帶任何欄位 → 回 `400 { "detail": "No fields to update" }`。
- `record_id` 不存在 → `404 { "detail": "travel_record record not found" }`。

```json
// Request 範例：核算完成後補寫里程與碳排
{ "distance_km": 165.4, "co2e_kg": 5.79, "status": "confirmed" }
```

---

## 4. `GET /api/travel-records` / `GET /api/travel-records/{record_id}`

- `GET /api/travel-records?limit=100&offset=0`：依 `created_at desc` 排序，**不過濾 `employee_id`**（見 §5 提醒，現況會回全體員工紀錄）。
- `GET /api/travel-records/{record_id}`：查無回 `404 { "detail": "travel_record record not found" }`。

---

## 5. 現況提醒（App 端整合前應留意）

- **GET/DELETE 端點目前未掛 `get_current_employee`**（`routers/eco_records.py:193`、`:222`），即不需 Bearer 也可呼叫，且 `GET /api/travel-records` 列表**不會依呼叫者過濾**、會回所有員工的紀錄。App 端若要做「我的差旅紀錄」列表，暫時需自行用回傳的 `employee_id` 欄位在前端過濾，或待後端補上依 token 過濾的版本——**不要假設列表已依身份範圍化**。
- `status` 欄位**無資料庫 enum 約束、無狀態機**（`db/schema.sql:117` 僅 `text not null default 'pending'`），App 端若要用它驅動 UI（如「待確認／已確認」），需與後端另行約定允許值，目前程式碼不會擋任意字串。
- `factor_id` / `co2e_kg` 為選填，代表**碳排量核算目前不是後端強制在建立當下完成**；App 若已完成前端核算可直接帶入 `co2e_kg`，否則後端不會自動代算（無 trigger／背景任務對應）。
- 完整欄位與型別以 `routers/eco_records.py` 的 `TravelRecordCreate` / `TravelRecordUpdate`（Pydantic model）為準，本文件為求可讀性做了摘要，異動時請重新核對程式碼。

---

## 附註：不屬本文件範圍

- OCR／GPT-4o NER／TDX 里程查詢／Google Maps 換算的實作細節：屬 App 端或前處理服務，非本後端端點契約。
- 認證與 401 攔截器機制：見 `Eco-Sensing_App_驗證機制_開發參考.md`。
- 差旅碳排如何併入月度統計、EXP／碳幣、Shared Savings：屬計算與遊戲化模組，非本端點契約範圍。

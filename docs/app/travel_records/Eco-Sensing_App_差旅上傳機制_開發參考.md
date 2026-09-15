# Eco-Sensing App 差旅（travel-records）上傳機制 — 開發參考

> 目的：彙整 **App 端（Flutter 員工端）** 開發「差旅碳核算上傳」所需的 API 形狀，供實作對齊。
> 權威出處：`Eco-Sensing_專案context文件_v28.md` §4.1（規格、[D2] 稽核流程與 preview 端點決議）、§5.1（`travel-records` 端點清單）、§8.1（App 掃描頁規格）；App 端收據確認對話框欄位：`docs/app/receipt_confirmation_fields_0915.md`；程式碼出處：`routers/eco_records.py`、`db/schema.sql`。
> 認證機制細節（登入、雙 token、401 攔截器）不重述，見 `Eco-Sensing_App_驗證機制_開發參考.md`；本文件假設 App 已持有有效 `access_token`。

---

## 0. 一句話定位（v28 更新）

**OCR／GPT-4o NER／TDX 里程查詢／Google Maps 換算全部跑在後端**，App 掃描頁只是「拍照／選圖上傳入口」。完整流程為：

> **App 拍照上傳 → 後端 OCR＋NER →（可選）`POST /api/travel-records/preview` 試算里程／碳排 → App 顯示稽核清單供員工人工確認／editable → 員工確認送出 → `POST /api/travel-records`（後端以最終值重算一次里程／碳排、不採信前端帶回值）→ 入庫**

**⚠️ 現況實作提醒**：本次僅落地 `TravelRecordCreate` / `TravelRecordUpdate` 的**輸入欄位形狀**（見 §2），尚未實作：OCR／NER 管線、`POST /api/travel-records/preview` 試算端點、里程/碳排的後端自動計算、`entry_source` 三態標記寫入。目前建立紀錄後 `co2e_kg` 恆為 `null`（顯示「尚未計算」），`distance_km` 需由 App 端在確認畫面帶入（無論正常或 degraded），因後端尚未有自動覆寫邏輯。App 端開發可先依本文件欄位形狀對接，實際計算生效時機另行公告。

---

## 1. 欄位可編輯性（與 App 收據確認對話框一致）

依 §4.1 [D2](6) 與 `receipt_confirmation_fields_0915.md` 定案：

| 欄位 | 對應 API 欄位 | 可編輯性 | 說明 |
| ------ | ------ | ------ | ------ |
| 票據類型 | `transport_mode` | **可編輯**（下拉選單） | 選項：`高鐵電子票`／`App乘車截圖`／`計程車紙本收據`／`其他`。**此欄位語意已從「交通工具代碼」改為「票據類型」**，取代舊版 `track_type` |
| 票據日期 | `travel_date` | **可編輯**（日期選擇器，僅年月日） | App 顯示格式 `yyyy/MM/dd hh:mm a`，落 API 僅取日期部分（`YYYY-MM-DD`） |
| 起站 | `origin` | **可編輯**（文字輸入框） | |
| 訖站 | `destination` | **可編輯**（文字輸入框） | |
| 金額 | `amount` | **可編輯**（數字輸入框，NT$） | 現為**必填**（非 nullable），對應 App `_totalFeeController` 型別 `double` |
| 里程 | `distance_km` | **條件式可編輯**：正常情形唯讀（顯示 TDX／Maps 換算結果）；**唯 degraded（換算失敗）時開放手填** | 現況實作尚未有後端計算，App 端暫時一律自行帶值，見 §0 提醒 |
| 碳足跡（預估） | `co2e_kg` | **一律唯讀，全由後端計算** | `POST`/`PATCH` **不接受 client 指定**，帶了也會被忽略；`null` 時 App 顯「尚未計算」 |
| 預估獎勵（經驗值／碳幣） | — | 唯讀 | 非本端點欄位，屬遊戲化模組（§8.1 App1.7），不在 `travel_record` 表內 |

**不得帶欄位**（一律由後端處理，client 傳入無效或會被忽略）：

- `employee_id`：由 `Authorization: Bearer` 解出（[A3] 全系統鐵律）
- `co2e_kg`：衍生值，一律後端計算，開放手填等同開作弊後門（[D2](6)）
- `factor_id`：排放係數列由後端依 `transport_mode`／`travel_date` 內部查找，App 不需知道也不應指定
- `id` / `created_at` / `updated_at`：資料庫自動產生
- `entry_source`：三態來源標記（`ai`／`ai_edited`／`manual`），由後端依「AI 預填是否被員工修改」自動判定寫入，**App 不傳此欄位**（現況實作尚未落地此邏輯，見 §0）

---

## 2. 端點總覽

| Method | 路徑 | 認證 | 用途 |
| ------ | ---- | ---- | ---- |
| `GET` | `/api/travel-records` | 不需 Bearer（現況程式碼未掛，見 §6 提醒） | 列表（分頁） |
| `POST` | `/api/travel-records/preview` | 需 `Bearer` | **試算里程/碳排、不落庫**（§4.1 [D2](5)）——**尚未實作**，見 §0／§5 |
| `POST` | `/api/travel-records` | **需 `Bearer`** | 建立一筆差旅紀錄，`employee_id` 由 token 解出並自動寫入 |
| `GET` | `/api/travel-records/{record_id}` | 不需 Bearer | 取單筆 |
| `PATCH` | `/api/travel-records/{record_id}` | **需 `Bearer`** | 修正既有紀錄（不改 `employee_id`） |
| `DELETE` | `/api/travel-records/{record_id}` | 不需 Bearer | 刪除（現況無擁有者檢查，見 §6） |

---

## 3. `POST /api/travel-records`

### Request Header

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request Body（對應 `TravelRecordCreate`，`routers/eco_records.py`）

| 欄位 | 型別 | 必填 | 說明 |
| ------ | ------ | ------ | ------ |
| `transport_mode` | string | **必填** | 票據類型：`高鐵電子票`／`App乘車截圖`／`計程車紙本收據`／`其他` |
| `travel_date` | date（`YYYY-MM-DD`） | **必填** | 票據日期 |
| `origin` | string \| null | 選填 | 起站 |
| `destination` | string \| null | 選填 | 訖站 |
| `amount` | number | **必填** | 金額（NT$） |
| `distance_km` | number \| null | 選填 | 里程（km）；正常情形應由後端計算覆寫，僅 degraded fallback 時採用此值（現況見 §0 提醒） |
| `receipt_id` | string \| null | 選填 | 綁定的報銷單據 ID |
| `status` | string | 選填，預設 `"pending"` | 紀錄狀態；**無 enum 限制與狀態機邏輯** |

> **不得帶欄位**：`employee_id`、`co2e_kg`、`factor_id`、`entry_source`（見 §1）。

### Request 範例

```json
// 軌 A：高鐵電子票
{
  "transport_mode": "高鐵電子票",
  "travel_date": "2026-09-14",
  "origin": "台北",
  "destination": "台中",
  "amount": 700,
  "distance_km": 165.4,
  "receipt_id": "EXP-2026-0914-01"
}
```

```json
// 軌 B：計程車紙本收據（員工手填起訖）
{
  "transport_mode": "計程車紙本收據",
  "travel_date": "2026-09-14",
  "origin": "台北車站",
  "destination": "南港軟體園區",
  "amount": 320,
  "distance_km": 8.2,
  "receipt_id": "EXP-2026-0914-02"
}
```

```json
// 軌 C：App 乘車截圖
{
  "transport_mode": "App乘車截圖",
  "travel_date": "2026-09-14",
  "origin": "信義區",
  "destination": "內湖科技園區",
  "amount": 280,
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
  "transport_mode": "高鐵電子票",
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

> `co2e_kg` 目前恆為 `null`（計算引擎未落地，見 §0）。App 端「碳足跡（預估）」欄位在收到 `null` 時應顯示「尚未計算」，**不可自行代算或以前端試算值頂替入庫值**。

### 錯誤情況

| 狀況 | 回應 |
| ------ | ------ |
| 缺 `Authorization` header | `401 { "detail": "Missing bearer token" }` |
| Access token 過期 | `401 { "detail": "Access token expired" }`（帶 `WWW-Authenticate: Bearer`）→ 走 401 攔截器換發＋重放 |
| Access token 無效／格式錯 | `401 { "detail": "Invalid access token" }` |
| 缺必填欄位（`transport_mode` / `travel_date` / `amount`）或型別錯 | `422`（FastAPI/Pydantic 自動驗證） |

---

## 4. `PATCH /api/travel-records/{record_id}`（修正既有紀錄）

- Header 同上需 `Bearer`；欄位皆選填（對應 `TravelRecordUpdate`，僅送要改的欄位），欄位集合與 §3 相同（不含 `co2e_kg`／`factor_id`／`entry_source`）。
- 全部欄位皆為 `None` / 不帶任何欄位 → 回 `400 { "detail": "No fields to update" }`。
- `record_id` 不存在 → `404 { "detail": "travel_record record not found" }`。

```json
// Request 範例：稽核後修正起訖點
{ "origin": "台北車站", "destination": "台中車站" }
```

---

## 5. `POST /api/travel-records/preview`（試算端點，§4.1 [D2](5) — 尚未實作）

> 依 v28 §5.1／§4.1 定案應提供，**目前程式碼尚未有此路由**，此處先記錄目標形狀供實作對齊，App 端串接前請先確認後端是否已補上。

- 認證：需 `Bearer`（防匿名濫打 TDX／Maps 配額），但**不落庫、不碰 `employee_id`、不定 `entry_source`**。
- Request：`origin`／`destination`／`transport_mode`／`travel_date`。
- Response 200：`distance_km`／`co2e_kg`／`factor_id`（純回傳，App 僅用於確認畫面顯示）。
- **degraded 降級**：TDX／Maps 查不到里程（地名無法解析／外部 API 中斷）時回 `HTTP 200` ＋ 空 `distance_km`/`co2e_kg` ＋ `"degraded": true` 旗標，**非 4xx/5xx**；App 收到 `degraded: true` 才開放里程欄手填（見 §1）。
- preview 回傳值僅供顯示，**送出 `POST /api/travel-records` 時後端會重算**，不會採信 preview 帶回的值（防竄改）。

---

## 6. 現況提醒（App 端整合前應留意）

- **本次未落地項目**（見 §0）：OCR／NER 管線、`preview` 試算端點、里程/碳排後端自動計算、`entry_source` 寫入邏輯。App 端目前仍需自行完成里程換算並帶值於 `distance_km`；`co2e_kg` 恆回 `null`。
- **GET/DELETE 端點目前未掛 `get_current_employee`**，即不需 Bearer 也可呼叫，且 `GET /api/travel-records` 列表**不會依呼叫者過濾**，會回所有員工的紀錄；`DELETE` 亦無擁有者檢查，任何人可刪任意紀錄（v28 §5.1 已列為 P1 待補項目）。App 端「我的差旅紀錄」列表暫時需自行以回傳的 `employee_id` 過濾。
- `status` 欄位**無資料庫 enum 約束、無狀態機**（`db/schema.sql` 僅 `text not null default 'pending'`），App 若要用它驅動 UI，需與後端另行約定允許值。
- 完整欄位與型別以 `routers/eco_records.py` 的 `TravelRecordCreate` / `TravelRecordUpdate`（Pydantic model）為準，本文件為求可讀性做了摘要，異動時請重新核對程式碼。

---

## 附註：不屬本文件範圍

- OCR／GPT-4o NER／TDX 里程查詢／Google Maps 換算的實作細節：屬後端計算引擎（尚未實作），非本端點契約現況範圍。
- 認證與 401 攔截器機制：見 `Eco-Sensing_App_驗證機制_開發參考.md`。
- 差旅碳排如何併入月度統計、EXP／碳幣、Shared Savings：屬計算與遊戲化模組，非本端點契約範圍。

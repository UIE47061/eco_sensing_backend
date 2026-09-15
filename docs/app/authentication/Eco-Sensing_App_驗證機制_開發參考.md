# Eco-Sensing App 驗證機制 — Claude Code 開發參考

> 目的：彙整 **App 端（Flutter 員工端）** 為身份驗證機制須導入的內容，供 Claude Code 依此實作。
> 權威出處：`Eco-Sensing_專案context文件_v25.md` §8.4、§5.1 [D5]、§8.5 [A1][A2][A3]、§4.4.4（效期表）。
> 本文件為落地清單；設計理由（為何雙 token 而非單枚 JWT）見 [D5] v0.24 決議子段，此處不重述。

---

## 0. 一句話定位

App 目前是**純前端登入**——登入頁不驗帳密、選「員工端」即進、`DemoAuthStorage` 僅以 `SharedPreferences` 存一個布林登入狀態、後端對此一無所知。驗證機制的工作，就是把這層假登入換成**後端簽發的雙 token**，並讓冷啟動達成「打開即進、長期免登入」。列為 **P1 前置工作**。

---

## 0.1 開發順序（先後端、再 App）

> 現況：ERD／資料庫尚未修改、API 端點尚未架設。經評估採**後端先行**。

**決定**：先做後端 P1 auth 薄切片，Swagger 驗證通過後，再導入 App 端驗證邏輯。**不採** App 先行＋mock。

**順序**：

1. **Schema 建置（§6 已定案）**：`APP_SESSION` 建表（存 App Refresh 的 `refresh_token_hash`）、`EMPLOYEE` 補 `password_hash`、刪 `EMPLOYEE.id_token`。
2. **後端薄切片**：`POST /api/auth/login`（驗 `password_hash` → 簽發 Access + Refresh、寫 `APP_SESSION`）→ 換發端點（比對 `APP_SESSION.refresh_token_hash`）→ `get_current_employee` dependency（自 `Bearer` 解出 `employee_id`）。
3. **Swagger 驗證**：無需 client 即可跑完 login → 401 過期 → refresh → 撤銷 全生命週期。
4. **再做 App**：串真登入、Refresh 移入 `flutter_secure_storage`、冷啟動靜默續期、401 攔截器——皆對**真的會回 401／輪換真 token 的後端**開發。

**為何後端先行（本專案脈絡）**：App 端最難的是靜默續期／401-重放／操作中途保存等有狀態邏輯，對「真的回 401 的後端」開發遠比對 mock 容易——用 mock 等於把 token 狀態機做兩次（stub 裡假造一次、App 裡消費一次）。因本專案為**同一人序列開發**，mock 無法解鎖並行、且是用完即棄的額外負擔，還可能與真契約漂移，故不採。[D5]「介面形狀須正確」由真 `get_current_employee` 從第一天就強制 `employee_id` 只從 token 解出而自然滿足，無假流程須事後拆除。

**唯一注意**：後端先行須守住 P1 範圍——只做 `login` ＋ 換發 ＋ `get_current_employee`，**先別**順手接四大模組寫入端點；auth dependency 是四模組日後共用的那塊，先單獨證通即達目的。

---

## 0.2 測試帳號管理（P1 建帳實務）

> 原則：測試期可在「帳號好記、密碼好打、一鍵重灌」上求方便，但**不可在儲存方式或驗證流程上破格**——否則測到的是日後要拆掉的假流程（同 [D5] 警告）。

**不可妥協**

- 密碼**一律經 bcrypt／argon2 雜湊後**才寫入 `EMPLOYEE.password_hash`，**絕不存明文**。測試密碼可以是 `test1234`，但進資料庫時必須是 hash。
- 一律走正式的 `POST /api/auth/login` 驗證，**不得為測試「略過密碼驗證、隨便填都能進」**——那正是現況 demo 登入要被拆掉的問題。

**做法約定**

1. **用 seed 腳本產生，不手動 INSERT**：寫 `seed_test_accounts.py`，內含測試帳號 email＋明文密碼，腳本執行時**呼叫與 `login` 同一套 hash utility**把密碼雜湊後寫入 `password_hash`。好處：可重現、一鍵重灌（資料庫常重建時尤重要）、資料庫內永遠是 hash。
2. **產 hash 與驗 hash 用同一套函式**：seed 時**別走 PostgREST 直接 INSERT 自算的 hash**，以免與後端 `login` 的雜湊參數／版本不一致；應 import 後端同一個 hash utility（或呼叫後端建帳路徑）。
3. **測試帳號可識別、可清除**：email 用固定網域慣例（如 `alice@test.local`），上線前一句 `DELETE FROM employee WHERE email LIKE '%@test.local'` 即整批清除，不混入正式資料。（不想動 schema 就靠 email 慣例；若可動則加 `EMPLOYEE.is_test` 布林。）
4. **明文密碼不進版控**：seed 腳本若進 git，明文密碼改從環境變數／`.env` 讀（`.env` 入 `.gitignore`），因 git 歷史永久留存、事後難清。

**Supabase 提醒**

- 本專案自管 `EMPLOYEE.password_hash`（雙 token 全自簽、須與 `employee_id` 歸戶），**不使用 Supabase Auth（`auth.users`）**；勿混用兩套身份來源。測試帳號一律進自有 `EMPLOYEE` 表。

---

## 1. 定案參數（不可改，與 §8.4 / §4.4.4 同源）

| 項目 | 值 | 儲存 / 備註 |
| ------ | ----- | ----------- |
| App Access Token exp | **1 小時** | 不落庫；由 App Refresh 換發；每個歸戶請求帶 `Authorization: Bearer` |
| App Refresh Token exp | **30 天（不輪換）** | 存 `flutter_secure_storage`；後端只存 `refresh_token_hash`；到期重登 |

- 效期**與「月結算」無關**，30 天純為體驗/風險折衷，同以月為單位僅屬巧合。
- Refresh **不啟用輪換**（列 P3）。
- 與 Eco-Agent 雙 token **同構**，差別僅觸發情境：Agent 背景常駐、App 冷啟動。

---

## 2. 全系統硬性原則（[A3] / [D5]）

**`employee_id` 一律由憑證（token）解出，不得出現在任何 request body。**

- body 只帶業務參數；身份只從 `Authorization` header 的 token 解出。
- 四大模組（差旅 / 廢棄物 session / 電梯 / Eco-Agent）payload 皆含 `employee_id`，若由 client 指定＝任何人可把碳排寫到任何人名下；歸戶又連動 EXP／碳幣／Shared Savings，可偽造即誘因失效。
- App 各端點同樣適用。**這是介面形狀的鐵律，P1 即使用臨時憑證也必須維持。**

---

## 3. App 端須導入的四塊工作

### 3.1 真實登入（取代 demo 登入）

- 登入頁改呼叫 **`POST /api/auth/login`**，body 帶 `email` + `password`。
- 成功回應含 **Access Token + Refresh Token**（雙 token 一次簽發）。
- 移除「選員工端即進」的捷徑；`DemoAuthStorage` 的布林狀態改為「持有有效 Refresh」判定。
- 企業端 Vue 後台同為不驗帳密現況，但本文件聚焦員工端 Flutter；企業端認證另議。

### 3.2 憑證儲存

- **Refresh Token → `flutter_secure_storage`**（Android Keystore / iOS Keychain）。
- **絕不放 `SharedPreferences`**（現況 demo 就是放這裡，須改掉）。
- Access Token 保留於記憶體 / 短期即可，**不需持久化、不落庫**。

### 3.3 冷啟動靜默續期（對應 §App1.0「自動判斷已登入」）

冷啟動流程：

1. 讀 `flutter_secure_storage` 的 Refresh Token。
2. 有效且未撤銷 → **背景靜默向後端換發新 Access → 直接進主畫面（員工無感）**。
3. 換發時**無網路** → 先進 App 看快取、待有網再補換，**不卡在登入頁**。
4. 讀不到 / 過期 / 已撤銷 → 導向登入頁。

### 3.4 401 驅動的續期攔截器（過期判定權在後端）

- 每個歸戶請求帶 `Authorization: Bearer <Access>`。
- **有效性判定權在後端**（`get_current_employee` 每請求驗簽 + 驗 `exp`，過期回 `401`）。
- App 讀 `exp` **僅作 UX 預判**（提前引導），實際續期 / 重登以**收到 `401`** 觸發。
  （App 為不可信一方、無簽章密鑰，不能自行判定有效性。）
- 攔截器行為：收到 `401` → 用 Refresh 換發新 Access → **重放原請求**；換發也回 `401/403` → 清憑證、導登入頁。
- **操作中途過期**：暫存當前操作、重登後復原，避免丟失使用者填寫內容。

---

## 4. App 端依賴的後端端點（P1 範圍）

> App 只需知道呼叫這些端點；後端實作屬 §5.1 P1，非本文件重點，僅列供對齊。

| 端點 | 呼叫者 / 認證 | 用途 |
| ------ | ------------ | ------ |
| `POST /api/auth/login` | App，帶 email + password | 驗帳密 → 簽發 App Access + App Refresh |
| （換發端點）App token refresh | App，帶 Refresh Token | 比對 `refresh_token_hash` 且未撤銷 → 發新 Access；已撤銷回 `401/403` |
| 所有歸戶端點 | App，帶 `Bearer <Access>` | 經 `get_current_employee` dependency 解出 `employee_id` |

> 換發端點路徑已定案並實作：`POST /api/auth/token/refresh`；語意比照 Eco-Agent 的 `POST /api/agent/token/refresh`。

### 4.1 Base URL（本機測試 vs 部署環境）

| 環境 | Base URL | 說明 |
| ------ | ---------- | ------ |
| 本機開發（Swagger／curl，開發機本身） | `http://127.0.0.1:8000`（`uvicorn app:app --reload` 預設）或 `http://127.0.0.1:7860`（`python app.py`，依 `Env.PORT`） | 依啟動方式而定，以終端機實際印出的 port 為準，不要假設固定值 |
| App 對本機後端（Android 模擬器） | `http://10.0.2.2:<port>` | 模擬器的 `localhost` 指向模擬器自身，須用 `10.0.2.2` 才能連回宿主機 |
| App 對本機後端（iOS 模擬器） | `http://127.0.0.1:<port>` 或 `http://localhost:<port>` | iOS 模擬器與宿主機共用網路棧，可直接用 localhost |
| App 對本機後端（實機、同區網） | `http://<開發機區網 IP>:<port>` | 例如 `http://192.168.1.23:8000`；手機與開發機須在同一 Wi-Fi |
| **部署後（正式）** | **`https://uie47061-eco-sensing-backend.hf.space`** | Hugging Face Space；App release 版與交付測試一律打此網址 |

- **App 端須把 base URL 做成可切換的環境設定**（如 `--dart-define`、build flavor、`.env`），**不可寫死在程式碼裡**；本機測試／部署環境間只切設定值，端點路徑本身兩邊相同（如 `/api/auth/login`）。
- `/docs`、`/redoc`、`/openapi.json` 兩環境皆掛 HTTP Basic Auth（`DOCS_USERNAME`/`DOCS_PASSWORD`），僅影響人工用 Swagger 頁面測試時的登入；App 執行期呼叫的一般端點（`/api/...`）不受此限、不需帶這組帳密。
- **CORS 提醒**：`app.py` 目前允許的 origin 僅 `localhost:5173`／`127.0.0.1:5173`／`huggingface.co`（給 Vue 企業後台用）。App 若以原生 iOS/Android 執行**不受 CORS 限制**（CORS 只作用於瀏覽器內的 fetch/XHR）；但若改以 **Flutter Web** 建置測試，須另將該 dev server 的 origin 加進後端 CORS 清單，否則請求會被瀏覽器擋下（回應到得了、但瀏覽器不轉交給 JS）。

### 4.2 端點封包結構（Request / Response，依現行程式碼 `routers/auth.py`）

**`POST /api/auth/login`** — 不需 Bearer

```json
// Request
{ "email": "alex@example.com", "password": "test1234" }
```

```json
// Response 200
{
  "access_token": "<JWT>",
  "refresh_token": "<64B url-safe 亂數字串>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

```json
// Response 401（帳密錯，帳號不存在／未設密碼／密碼不符皆回同一訊息，不洩漏帳號是否存在）
{ "detail": "Invalid email or password" }
```

App 端對應動作：`access_token` 存記憶體、後續請求帶 `Authorization: Bearer <access_token>`；`refresh_token` 寫入 `flutter_secure_storage`；`expires_in`（秒，固定 3600＝1 小時）僅供 UX 預判提前引導，**不得**用它自行判定 token 是否有效（§3.4，判定權在後端）。

**`POST /api/auth/token/refresh`** — 不需 Bearer，改帶 Refresh Token

```json
// Request
{ "refresh_token": "<存於 flutter_secure_storage 的值>" }
```

```json
// Response 200（注意：不回新的 refresh_token——§1 定案不輪換，App 端 Refresh 原值不變、不覆寫）
{ "access_token": "<新 JWT>", "token_type": "bearer", "expires_in": 3600 }
```

```json
// Response 401（refresh 不存在或已撤銷）
{ "detail": "Refresh token invalid or revoked" }
```

```json
// Response 401（refresh 已過期，30 天到期）
{ "detail": "Refresh token expired" }
```

App 端對這兩種 401 的處理相同：清除本機憑證（含 secure storage 內的 refresh token）、導向登入頁（對應 §3.4 攔截器換發失敗分支、§5 撤銷承受）。

**歸戶端點（帶 `Authorization: Bearer <access_token>`）的通用行為**

- Access 過期或簽章/格式錯誤 → 一律 `401`，`detail` 為 `"Access token expired"` 或 `"Invalid access token"`，並帶 `WWW-Authenticate: Bearer` header。App 攔截器**不需解析 detail 文字差異**，見到 `401` 即觸發「換發＋重放原請求」（§3.4）。
- 缺 `Authorization` header → `401 Missing bearer token`。
- P1 範圍內、App 會以 Bearer 呼叫的四個寫入端點（`employee_id` 皆由後端從 token 解出並自動寫入，**App body 絕不帶 `employee_id`**，對應 §2 鐵律）：

  | 端點 | 對應模組 | Request body 必要欄位（其餘見程式碼為選填） |
  | ------ | ---------- | ---------------------------------------------- |
  | `POST /api/travel-records` | 差旅 | `transport_mode`、`travel_date` |
  | `POST /api/waste-sessions` | 廢棄物 session | `bin_id` |
  | `POST /api/elevator-trips` | 電梯 | `ts_in`、`floor_in`、`floor_out` |
  | `POST /api/digital-usages` | 用紙量手動上傳 | `usage_date`、`print_pages`（≥0） |

  > 完整欄位（含選填）以 `routers/eco_records.py` 對應 Pydantic model（`TravelRecordCreate` / `WasteSessionCreate` / `ElevatorTripCreate` / `DigitalUsageCreate`）為準，此處僅列 App 端必填。`/digital-usages` 為同員工同日的「後蓋前」語意：同一天重複上傳採更新既有紀錄，但若重送的 `collected_at` 比既有紀錄舊則不覆蓋（見程式碼註解 [D16]）。GET/PATCH/DELETE 端點供資料回顯與修正，非 A1–A6 這一輪主要範圍。
  >
  > `waste-bins`／`devices`／`waste-events` 三端點不掛 `get_current_employee`（由感測裝置／Eco-Agent 側寫入，非員工歸戶動作），App 工作區本次不需呼叫。

---

## 5. 撤銷（App 端須能承受）

- 員工離職 / 裝置遺失 → 後端把該 Refresh 標 `revoked`。
- 手上 Access 至多撐到自身過期（≤ 1h，窗口可接受）。
- 之後無法再以已撤銷 Refresh 換發（換發端點回 `401/403`）→ App 被導回登入頁。
- App 端無須主動輪詢撤銷狀態；靠 `401/403` 被動感知即可。

---

## 6. 建表 / Schema 定案（依此產 `schema.sql`）

> 以下為已定案，Claude Code 依此實作；ERD 見 `eco_sensing_erd.mmd`[^erd]。

- **`EMPLOYEE` 補 `password_hash`**（bcrypt / argon2）——[D5] P1 明列，作為密碼驗證的唯一憑據，只在 `login` 這一步比對，簽出 token 後不再使用。
- **App Refresh 的 `refresh_token_hash` 存新表 `APP_SESSION`（定案：開獨立表）**，不塞 `EMPLOYEE`。理由：Refresh 是「一筆一筆、有生命週期、可撤銷、單員工可多枚（多裝置）」的實體，非員工屬性；獨立表天然支援多裝置與個別撤銷，並與 `DEVICE_BINDING` 對 Eco-Agent 所做者同構。最小欄位：

  | 欄位 | 說明 |
  | ------ | ------ |
  | `id` PK | |
  | `employee_id` FK → `EMPLOYEE` | 歸屬員工 |
  | `refresh_token_hash` | 只存 hash，不存明文 token |
  | `status` | `active` / `revoked` |
  | `created_at` / `expires_at` / `last_used_at` / `revoked_at` | 生命週期與撤銷 |

- **`EMPLOYEE.id_token` 冗餘，刪除（定案）**。原用途不明、context §7 已列待釐清；經釐清確認為冗餘欄位，刪除以消除與 `DEVICE_BINDING.id_token`（裝置粒度、per-device、[D14] 鍵粒度所依賴）的同名混淆。
- **同名欄位 `refresh_token_hash`（`DEVICE_BINDING` 與 `APP_SESSION` 各有一枚）不需處理**：不同表、SQL 恆帶表名限定不會撞，且語意一致（皆為某枚 Refresh 的雜湊），同名恰當。
- **欄位語意註解於 `schema.sql` 以 `COMMENT ON` 落地（待辦）**：Mermaid ERD 無法承載欄位級顯示註解，語意說明改在 `schema.sql` 用 PostgreSQL 原生 `COMMENT ON COLUMN`，會存進資料庫 metadata（`\d+`、GUI 工具可見）。Claude Code 產 schema 時須補以下註解（文字可調整）：

  ```sql
  COMMENT ON COLUMN device_binding.id_token IS
    '裝置粒度憑證，per-device 一枚；4.4.3 事件 ID 與 [D14] 鍵粒度所依賴';
  COMMENT ON COLUMN device_binding.refresh_token_hash IS
    'Eco-Agent Refresh 的雜湊（裝置粒度）';
  COMMENT ON COLUMN app_session.refresh_token_hash IS
    'App Refresh 的雜湊（員工手機粒度）；與 device_binding.refresh_token_hash 同名、不同粒度';
  COMMENT ON COLUMN employee.password_hash IS
    '密碼雜湊（bcrypt/argon2）；僅 login 驗證用，簽出 token 後不再使用';
  ```

[^erd]: 資料庫結構參照文件：`eco_sensing_erd.mmd`（本次已同步——新增 `APP_SESSION`、刪除 `EMPLOYEE.id_token`、補 `EMPLOYEE.password_hash`；另依 context §4.4 [D14][D15] 對 `DIGITAL_USAGE` 新增 `printer_serial`／`printer_page_counter`、刪除 `print_pages`）。

---

## 7. 實作驗收判準（P1）

- [ ] 登入呼叫真 `POST /api/auth/login`，回雙 token。
- [ ] Refresh 存 `flutter_secure_storage`，`SharedPreferences` 不再存憑證。
- [ ] 冷啟動能以有效 Refresh 靜默進主畫面（無感）；無網先進看快取。
- [ ] 任一歸戶請求收到 `401` 能自動換發並重放；換發失敗才導登入。
- [ ] 全部歸戶請求 body **不含** `employee_id`，身份只從 header 解出。
- [ ] 撤銷後 App 於下次換發被 `401/403` 擋下、導回登入。

### 7.1 階段與步驟（依工作區劃分，先後端、再 App）

> 工作區分**後端**與 **App** 兩區,依「先後端、再 App」順序。標「跨兩端」者兩區各有分工,需雙方認領。「對應節次」指本文件內規格。狀態圖例:⬜ 未開始／🟡 進行中／✅ 完成。
> 註:B1 與 §0.1 步驟 1 為同一件事(Schema 建置)在不同章節的呈現,非兩份工作。

**後端工作區（先做，Swagger 驗證通過才進 App 區）**

| # | 階段 | 對應節次 | 工作區 | 狀態 |
| --- | ------ | ---------- | -------- | ------ |
| B1 | Schema 建置（`APP_SESSION` 建表、`EMPLOYEE` 補 `password_hash`／刪 `id_token`；`COMMENT ON` 註解） | §6、§0.1-1 | 後端 | ✅ |
| B2 | 後端薄切片：`POST /api/auth/login`（驗 `password_hash`→簽雙 token、寫 `APP_SESSION`）、換發端點、`get_current_employee` dependency | §0.1-2、§3.1 | 後端 | ✅ |
| B3 | `employee_id` 由 `Bearer` 解出、各歸戶端點強制不信 body | §2 | 後端（App 僅配合 body 不帶身份） | ✅ |
| B4 | 撤銷簽發：離職／遺失標 `APP_SESSION.status=revoked`、換發回 `401/403` | §5 | 後端（App 承受，見 A5） | ✅ |
| B5 | 測試帳號 seed（雜湊寫入、可清除 email 慣例、明文不進版控） | §0.2 | 後端 | ✅ |
| B6 | Swagger 驗證：login→401 過期→refresh→撤銷 全生命週期跑通 | §0.1-3 | 後端 | ✅ |

**App 工作區（後端 Swagger 驗證通過後才開始）**

| # | 階段 | 對應節次 | 工作區 | 狀態 |
| --- | ------ | ---------- | -------- | ------ |
| A1 | 真實登入:串接 `POST /api/auth/login`、移除 demo 捷徑 | §3.1、§0.1-4 | App | ⬜ |
| A2 | 憑證儲存:Refresh 改存 `flutter_secure_storage` | §3.2 | App | ⬜ |
| A3 | 冷啟動靜默續期(含無網看快取) | §3.3 | App | ⬜ |
| A4 | 401 驅動續期攔截器(換發＋重放、操作中途保存) | §3.4 | App | ⬜ |
| A5 | 撤銷承受:收 `401/403` 導回登入(對應後端 B4) | §5 | App（後端 B4 提供） | ⬜ |
| A6 | 歸戶請求配合:body 不帶 `employee_id`(對應後端 B3) | §2 | App（機制在後端 B3） | ⬜ |

### 7.2 修訂章節（若未來須補做）

> 供 §7.1「階段與步驟」新增列時參照。以下項目本次不列 P1，若日後啟用，於 7.1 表格加對應列並標狀態。

| 修訂項目 | 對應節次 | 觸發條件 |
| ---------- | ---------- | ---------- |
| 密碼重設流程 | 附註 | 需求納入或安全稽核要求 |
| 帳號鎖定（連續失敗） | 附註 | 需求納入或安全稽核要求 |
| Refresh 輪換（每次續期換發、舊的作廢） | §1、附註 | P3 資安強化啟動 |
| 企業端（Vue 後台）後端認證 | §3.1 | 企業端脫離 demo 登入 |
| `APP_SESSION` 加裝置識別欄（`device_label` 等） | §6 | 多裝置登入需在列表中辨識來源裝置 |

---

## 附註：不屬 App 端本次範圍

- 密碼重設、帳號鎖定：列 P3。
- Refresh 輪換：不啟用，列 P3。
- Eco-Agent 綁定鏈（binding code / device_secret / 四端點）：屬 Agent 側，見 §4.4.2，非 App 驗證機制本身。

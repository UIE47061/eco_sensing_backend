# 收據確認對話框欄位資訊

| 欄位 (UI 標籤) | 對應變數 | 型別 | 是否可編輯 | 說明 |
|---|---|---|---|---|
| 票據類型 | `_selectedReceiptType` | `String` | 可編輯（下拉選單） | 選項：高鐵電子票、App乘車截圖、計程車紙本收據、其他 |
| 票據日期 | `_selectedDate` | `DateTime` | 可編輯（日期選擇器，僅改年月日） | 顯示格式 `yyyy/MM/dd hh:mm a` |
| 起站 | `_originController` | `String` | 可編輯（文字輸入框） | hint「輸入起站地址」 |
| 訖站 | `_destinationController` | `String` | 可編輯（文字輸入框） | hint「輸入訖站地址」 |
| 里程 | `_distanceController` | `double?` | 可編輯（數字輸入框） | 單位 km；顯示 TDX／Google Maps 換算結果，換算失敗（degraded）時作為人工輸入 fallback |
| 金額 | `_totalFeeController` | `double` | 可編輯（數字輸入框） | 單位 NT$ |
| 碳足跡（預估） | `widget.estimatedCarbonFootprint` | `double` | 唯讀 | 顯示後端計算結果的 preview |
| 預估獎勵 - 經驗值 | `widget.experienceGain` | `int` | 唯讀 | 顯示格式 `{值} Exp` |
| 預估獎勵 - 碳幣 | `widget.coinGain` | `int` | 唯讀 | 顯示格式 `{值} 碳幣` |

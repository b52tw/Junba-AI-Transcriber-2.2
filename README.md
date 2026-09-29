# Junba AI Transcriber v2.2

Windows 10/11 繁體中文 GUI：離線 `faster-whisper` + Google Gemini 3.5 Transcribe + M4A 切割/合併 + TXT/SRT/VTT/Word。

## v2.2 修正重點

- Google 設定頁新增「前往取得 API Key」與「測試 API Key」。
- 支援 Windows 檔案總管拖放多個音檔；檔案選擇器也可一次多選。
- 加入音檔後主動詢問切割方式：不切割 / 10 / 15 / 30 / 60 / 自訂分鐘。
- 修正 v2.1「看起來卡住」：v2.1 在 `split=0` 時是一整個檔案一個 chunk，而且整體進度只在 chunk 完成後更新；v2.2 將 Whisper 模型載入顯示為 indeterminate，轉錄時以 segment 結束時間 / 音檔總長度更新階段與整體百分比。
- 新增執行紀錄、階段進度、整體進度、checkpoint 位置。
- `停止` 會等背景工作真正結束後才重新開放開始按鈕，避免重複工作執行緒。
- Google Gemini 模式使用 `gemini-3.5-transcribe`。啟用 speaker diarization 或 word timestamps 時，長音檔會自動限制為最多 30 分鐘一段；未啟用這兩項時最多 60 分鐘一段。
- 混合模式：Whisper 本機轉錄，再把「文字」交給 Gemini 整理；音訊不上傳。
- 標準離線版尚未整合 pyannote，因此 UI 不再宣稱離線多人講者已完成。

## GitHub Actions 驗證

`.github/workflows/build-windows-v2.2.yml` 會在 `windows-latest`：

1. 安裝 Python 3.11 x64 與 requirements。
2. `compileall` + 套件 import smoke test。
3. 用 FFmpeg 實際建立、讀取、合併測試音檔。
4. 建立 Single EXE。
5. **在 Windows runner 實際執行 Single EXE `--self-test`**。
6. 建立 Portable EXE。
7. **在 Windows runner 實際執行 Portable EXE `--self-test`**。
8. 只有自我檢查通過才上傳 Artifact。

因此這版比 v2.1 多了一層「Windows 上真的把 EXE 跑起來檢查必要元件」的門檻。

## 使用方式

1. 加入或拖曳音檔。
2. 加入後選擇是否切割。
3. 選擇離線 Whisper / Google Gemini / 混合模式。
4. 第一次使用前可到「設定 → 執行環境檢查」。
5. Google 模式先到「設定 → 前往取得 API Key」，貼上後按「測試 API Key」。
6. 按開始後觀察「目前階段 %」「整體進度 %」與執行紀錄。

## 完全離線 large-v3

`large-v3` 不內嵌在 EXE。第一次可讓 faster-whisper 下載，或先執行 `download_large_v3.bat`，之後在 GUI 指定 `models\large-v3`。指定本機模型後即可斷網轉錄。

## CUDA

程式會透過 CTranslate2 偵測 CUDA；有可用 NVIDIA CUDA 時使用 GPU/float16，否則退回 CPU/int8。實際 CUDA DLL 相容性仍需在目標 Windows 電腦檢查，因此設定頁新增「執行環境檢查」。

## 隱私

- 離線 Whisper：音訊不離開電腦。
- 混合模式：音訊不離開電腦，只把 Whisper 產生的文字送至 Gemini。
- Google Gemini：音訊會上傳 Google API。

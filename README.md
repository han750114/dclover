#  Lover-Bot-Discord

## 專案簡介

Lover-Bot-Discord 是一個先進的 Discord 機器人專案，結合了大型語言模型（LLM）的強大能力、持久的記憶管理和主動關懷機制。我們的目標是打造一個能夠在 Discord 上與使用者進行**連續、有溫度、且個性化**的語音及文字互動的虛擬戀人。

這個專案是一個高階的 LLM 應用範例，結合了 RAG（檢索增強生成）概念中的記憶提取和複雜的異步排程任務。

## ✨ 核心功能（規劃中/已實現）

| 類別 | 功能名稱 | 狀態 | 說明 |
| :--- | :--- | :--- | :--- |
| **🧠 記憶與人格** | **一致的角色設定** |  實施中 | Bot 具有名為「小愛」的固定溫柔戀人人格和說話風格。 |
| | **長期記憶管理** |  實施中 | 使用 SQLite 資料庫儲存使用者的喜好、特別日子等關鍵資訊，並在對話中體現。 |
| **⏰ 主動關懷** | **排程通知** |  規劃中 | 定時（如早上/晚上）主動透過私訊發送客製化的問候和關心。 |
| | **環境感知** |  待開發 | 檢查使用者 Discord 狀態（如：正在玩遊戲、請勿打擾），以智慧調整訊息。 |
| **🗣️ 語音互動** | **Speech-to-Speech (S2S)** |  待開發 | 支援語音頻道通話，透過 STT 接收語音並透過 TTS 播放語音回覆。 |
| **🛠️ 互動介面** | **Slash Commands** |  規劃中 | 轉換為 Discord 斜線指令（`/ask`, `/remember`），提升用戶體驗。 |

---

## 🛠️ 快速設定指南 (Setup Guide)

要運行此專案，您需要 Python 3.8+ 環境、Git，以及必要的 API 金鑰。

### 1. 克隆專案

使用 Git 將專案克隆到您的本地電腦：

```bash
git clone https://github.com/han750114/dclover.git
cd dclover
```

2. 環境設定A. 建立虛擬環境與安裝依賴強烈建議使用虛擬環境來管理依賴：
```bash
# 建立虛擬環境

python -m venv venv
# 啟動虛擬環境 (macOS/Linux)
source venv/bin/activate
# 啟動虛擬環境 (Windows)
.\venv\Scripts\activate

# 安裝所有依賴套件
pip install -r requirements.txt
```
B. 取得 API 金鑰您必須取得以下兩個憑證：憑證取得來源用途Discord Bot TokenDiscord Developer Portal啟動機器人並連線到 Discord。OpenAI API KeyOpenAI 平台呼叫 LLM 服務，用於生成對話和記憶處理。

C. 設定 .env 檔案在專案根目錄中建立一個名為 .env 的檔案（此檔案已被 .gitignore 忽略，不會上傳），並填入您的金鑰：

```bash
# .env 檔案內容
DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
OPENAI_API_KEY="YOUR_OPENAI_API_KEY_HERE"
```

3. 運行機器人在虛擬環境已啟動的情況下，執行主程式：Bashpython main.py
如果成功，您將在終端機中看到 Bot 上線的提示訊息。
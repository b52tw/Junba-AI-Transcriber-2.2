@echo off
setlocal
cd /d %~dp0
if not exist .venv py -3.11 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install huggingface_hub
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-large-v3', local_dir='models/large-v3')"
echo.
echo large-v3 已下載到：models\large-v3
echo 在程式的「本機模型資料夾」選擇此資料夾，即可斷網辨識。
pause

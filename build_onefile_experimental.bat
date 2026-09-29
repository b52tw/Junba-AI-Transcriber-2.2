@echo off
setlocal
cd /d %~dp0
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 找不到 Python Launcher。請安裝 Python 3.11 x64。
  pause
  exit /b 1
)
if not exist .venv py -3.11 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python -m pip check || exit /b 1
rmdir /s /q build 2>nul
python -m PyInstaller --noconfirm --clean JunbaAITranscriber_onefile.spec
if not exist dist\Junba_AI_Transcriber_v2.2.exe (
  echo [ERROR] 單檔 EXE 打包失敗。
  pause
  exit /b 1
)
start /wait "" dist\Junba_AI_Transcriber_v2.2.exe --self-test "%CD%\SELFTEST_SINGLE.txt"
findstr /c:"SELFTEST_OK" SELFTEST_SINGLE.txt >nul || (
  echo [ERROR] 單檔 EXE 自我檢查失敗。
  type SELFTEST_SINGLE.txt
  pause
  exit /b 1
)
echo 完成：dist\Junba_AI_Transcriber_v2.2.exe
pause

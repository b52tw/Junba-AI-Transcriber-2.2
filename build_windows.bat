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
python -m compileall -q main.py app tests || exit /b 1
pip install pytest
pytest -q tests || exit /b 1
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
python -m PyInstaller --noconfirm --clean JunbaAITranscriber_portable.spec
if not exist dist\Junba_AI_Transcriber_v2.2_Portable\Junba_AI_Transcriber_v2.2.exe (
  echo [ERROR] 打包失敗，請查看上方訊息。
  pause
  exit /b 1
)
start /wait "" dist\Junba_AI_Transcriber_v2.2_Portable\Junba_AI_Transcriber_v2.2.exe --self-test "%CD%\SELFTEST_PORTABLE.txt"
findstr /c:"SELFTEST_OK" SELFTEST_PORTABLE.txt >nul || (
  echo [ERROR] EXE 自我檢查失敗。
  type SELFTEST_PORTABLE.txt
  pause
  exit /b 1
)
echo.
echo =============================================
echo 完成：dist\Junba_AI_Transcriber_v2.2_Portable\Junba_AI_Transcriber_v2.2.exe
echo SELFTEST_PORTABLE.txt = SELFTEST_OK
echo =============================================
pause

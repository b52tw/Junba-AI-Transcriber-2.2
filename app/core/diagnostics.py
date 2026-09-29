from __future__ import annotations
import os
import subprocess
import tempfile
from pathlib import Path
from app.core.audio_tools import ffmpeg_exe


def environment_report(output_dir: str = '', local_model_dir: str = '') -> tuple[bool, str]:
    lines = []
    ok = True

    def add(name, passed, detail=''):
        nonlocal ok
        ok = ok and passed
        mark = '✓' if passed else '✗'
        lines.append(f'{mark} {name}' + (f'：{detail}' if detail else ''))

    # ffmpeg
    try:
        exe = ffmpeg_exe()
        r = subprocess.run([exe, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=10)
        add('FFmpeg', r.returncode == 0, exe)
    except Exception as e:
        add('FFmpeg', False, str(e))

    # Core imports
    for module, label in [('faster_whisper', 'faster-whisper'), ('ctranslate2', 'CTranslate2'),
                          ('av', 'PyAV'), ('docx', 'Word 匯出'), ('google.genai', 'Google GenAI')]:
        try:
            __import__(module)
            add(label, True)
        except Exception as e:
            add(label, False, str(e))

    try:
        import ctranslate2
        count = ctranslate2.get_cuda_device_count()
        add('NVIDIA CUDA', True, f'偵測到 {count} 個 CUDA 裝置' if count else '未偵測到 CUDA，離線 Whisper 將使用 CPU')
    except Exception as e:
        add('NVIDIA CUDA', True, f'無法偵測，仍可使用 CPU：{e}')

    if local_model_dir:
        p = Path(local_model_dir)
        add('本機 Whisper 模型', p.is_dir(), str(p))
    else:
        lines.append('• 本機模型：未指定；第一次使用模型名稱時可能需要下載。')

    if output_dir:
        try:
            p = Path(output_dir); p.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=p, delete=True) as _:
                pass
            add('輸出資料夾可寫入', True, str(p))
        except Exception as e:
            add('輸出資料夾可寫入', False, str(e))

    return ok, '\n'.join(lines)

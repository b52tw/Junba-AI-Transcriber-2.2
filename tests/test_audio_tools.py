from pathlib import Path
import subprocess
from app.core.audio_tools import ffmpeg_exe, audio_duration_seconds, merge_audio


def make_tone(path: Path, seconds=1):
    subprocess.run([
        ffmpeg_exe(), '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000',
        '-t', str(seconds), '-c:a', 'pcm_s16le', str(path)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def test_ffmpeg_duration_and_merge(tmp_path):
    a = tmp_path / 'a.wav'; b = tmp_path / 'b.wav'; out = tmp_path / 'merged.m4a'
    make_tone(a, 1); make_tone(b, 1)
    assert 0.7 <= audio_duration_seconds(str(a)) <= 1.3
    merge_audio([str(a), str(b)], str(out))
    assert out.exists() and out.stat().st_size > 100
    assert audio_duration_seconds(str(out)) >= 1.5

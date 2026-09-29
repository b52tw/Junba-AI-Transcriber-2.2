from __future__ import annotations
from app.core.models import Segment, TranscriptResult
from app.core.audio_tools import audio_duration_seconds


class LocalWhisperProvider:
    def __init__(self, model_name='large-v3', device='auto', compute_type='auto'):
        from faster_whisper import WhisperModel
        if device == 'auto':
            device = 'cuda' if self._cuda_available() else 'cpu'
        if compute_type == 'auto':
            compute_type = 'float16' if device == 'cuda' else 'int8'
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self.device = device
        self.compute_type = compute_type

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import ctranslate2
            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False

    def transcribe(self, path: str, language: str | None = None, stop_flag=None, progress_cb=None, wait_cb=None) -> TranscriptResult:
        kwargs = dict(beam_size=5, vad_filter=True, word_timestamps=True)
        if language and language != 'auto':
            kwargs['language'] = language
        duration = audio_duration_seconds(path)
        if progress_cb:
            progress_cb(0, '準備 Whisper 推論')
        segments_gen, info = self.model.transcribe(path, **kwargs)
        segs: list[Segment] = []
        parts: list[str] = []
        for seg in segments_gen:
            if wait_cb:
                wait_cb()
            if stop_flag and stop_flag():
                break
            text = (seg.text or '').strip()
            if text:
                segs.append(Segment(float(seg.start), float(seg.end), text))
                parts.append(text)
            if progress_cb:
                pct = int((float(seg.end) / duration) * 100) if duration > 0 else min(99, len(segs))
                progress_cb(max(1, min(99, pct)), f'{float(seg.end):.1f}/{duration:.1f} 秒' if duration > 0 else f'{len(segs)} 段')
        if progress_cb:
            progress_cb(100, 'Whisper 轉錄完成')
        return TranscriptResult('\n'.join(parts), segs, getattr(info, 'language', None), f'faster-whisper ({self.device}/{self.compute_type})')

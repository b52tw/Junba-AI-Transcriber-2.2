from __future__ import annotations
import mimetypes
from app.core.models import Segment, TranscriptResult


def _seconds(value) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if s.endswith('s'):
        s = s[:-1]
    try:
        return float(s)
    except Exception:
        return 0.0


class GeminiProvider:
    TRANSCRIBE_MODEL = 'gemini-3.5-transcribe'
    POSTPROCESS_MODEL = 'gemini-3.8-flash'

    def __init__(self, api_key: str, model: str | None = None):
        if not api_key:
            raise ValueError('尚未設定 Gemini API Key')
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model or self.TRANSCRIBE_MODEL

    def transcribe(self, path: str, diarization=True, timestamps=True, smart=False,
                   language_codes=None, progress_cb=None) -> TranscriptResult:
        if progress_cb:
            progress_cb(5, '上傳音檔至 Google')
        uploaded = self.client.files.upload(file=path)
        if progress_cb:
            progress_cb(35, 'Google 已收到音檔，開始轉錄')
        if smart:
            mode = 'smart'
        else:
            mode = {'type': 'verbatim'}
            if diarization:
                mode['diarization_mode'] = 'speaker'
            if timestamps:
                mode['timestamp_granularities'] = ['word']
        cfg = {'transcription_config': {'language_codes': language_codes or [], 'mode': mode}}
        interaction = self.client.interactions.create(
            model=self.model,
            input=[{
                'type': 'audio',
                'uri': uploaded.uri,
                'mime_type': uploaded.mime_type or mimetypes.guess_type(path)[0] or 'audio/m4a',
            }],
            generation_config=cfg,
        )
        if progress_cb:
            progress_cb(90, '解析 Gemini 回傳內容')
        text = getattr(interaction, 'output_text', '') or ''
        words = []
        for step in getattr(interaction, 'steps', []) or []:
            for content in getattr(step, 'content', []) or []:
                for ann in getattr(content, 'annotations', []) or []:
                    if getattr(ann, 'type', None) == 'word_info':
                        words.append(ann)
        segs = self._group_words(words)
        if not segs and text:
            segs = [Segment(0.0, 0.0, text)]
        if progress_cb:
            progress_cb(100, 'Gemini 轉錄完成')
        return TranscriptResult(text=text, segments=segs, language=None, engine=self.model)

    @staticmethod
    def _group_words(words) -> list[Segment]:
        result: list[Segment] = []
        current = None
        for w in words:
            speaker = getattr(w, 'speaker', None) or 'spk_1'
            start = _seconds(getattr(w, 'start_offset', None))
            end = _seconds(getattr(w, 'end_offset', None))
            txt = str(getattr(w, 'text', '') or '').strip()
            if not txt:
                continue
            if current and current.speaker == speaker and start - current.end <= 1.2:
                current.end = end
                if txt[:1] in '，。！？,.!?;；:：':
                    current.text += txt
                else:
                    current.text += (' ' if current.text and current.text[-1:].isascii() and txt[:1].isascii() else '') + txt
            else:
                current = Segment(start, end, txt, speaker)
                result.append(current)
        return result

    def postprocess_text(self, text: str, target='繁體中文', progress_cb=None) -> str:
        if progress_cb:
            progress_cb(10, '送出文字整理要求')
        prompt = (
            '請整理以下語音逐字稿。保留原意，不自行補造事實；修正明顯標點與斷句，'
            f'輸出使用{target}。若有講者標記請保留。\n\n{text}'
        )
        r = self.client.models.generate_content(model=self.POSTPROCESS_MODEL, contents=prompt)
        if progress_cb:
            progress_cb(100, 'Gemini 文字整理完成')
        return getattr(r, 'text', '') or text

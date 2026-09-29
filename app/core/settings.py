from __future__ import annotations
from PySide6.QtCore import QSettings
import keyring

APP = 'JunbaAITranscriber'
SERVICE = 'JunbaAITranscriber-Gemini'
ACCOUNT = 'GEMINI_API_KEY'


def settings() -> QSettings:
    return QSettings('Junba', APP)


def save_api_key(value: str) -> None:
    value = value.strip()
    if value:
        keyring.set_password(SERVICE, ACCOUNT, value)
    else:
        try:
            keyring.delete_password(SERVICE, ACCOUNT)
        except Exception:
            pass


def load_api_key() -> str:
    try:
        return keyring.get_password(SERVICE, ACCOUNT) or ''
    except Exception:
        return ''

from __future__ import annotations
import os
import urllib.request
import urllib.error
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QThread, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QComboBox, QSpinBox, QCheckBox, QLineEdit, QProgressBar,
    QMessageBox, QGroupBox, QFormLayout, QTabWidget, QAbstractItemView, QDialog,
    QDialogButtonBox, QPlainTextEdit
)
from app.core.settings import settings, load_api_key, save_api_key
from app.core.worker import TranscribeWorker
from app.core.audio_tools import merge_audio, audio_duration_seconds
from app.core.diagnostics import environment_report

AUDIO_EXTS = {'.m4a','.mp3','.wav','.aac','.flac','.ogg','.mp4','.webm','.aiff','.opus'}
API_KEY_URL = 'https://aistudio.google.com/app/apikey'


class AudioListWidget(QListWidget):
    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setToolTip('可一次多選，也可從檔案總管拖曳多個音檔到這裡。')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = []
            for u in event.mimeData().urls():
                p = u.toLocalFile()
                if p and Path(p).suffix.lower() in AUDIO_EXTS:
                    paths.append(p)
            if paths:
                self.filesDropped.emit(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class ApiKeyTestWorker(QThread):
    done = Signal(bool, str)
    def __init__(self, key: str):
        super().__init__(); self.key = key
    def run(self):
        try:
            req = urllib.request.Request(
                'https://generativelanguage.googleapis.com/v1beta/models',
                headers={'x-goog-api-key': self.key, 'User-Agent': 'JunbaAITranscriber/2.2'},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                if 200 <= r.status < 300:
                    self.done.emit(True, 'API Key 驗證成功，可連線至 Gemini API。')
                else:
                    self.done.emit(False, f'Google 回應 HTTP {r.status}')
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403):
                self.done.emit(False, f'API Key 無效、未授權或專案限制（HTTP {e.code}）。')
            else:
                self.done.emit(False, f'Google API 回應錯誤（HTTP {e.code}）。')
        except Exception as e:
            self.done.emit(False, f'連線失敗：{e}')


class DiagnosticsWorker(QThread):
    done = Signal(bool, str)
    def __init__(self, output_dir: str, model_dir: str):
        super().__init__(); self.output_dir=output_dir; self.model_dir=model_dir
    def run(self):
        self.done.emit(*environment_report(self.output_dir, self.model_dir))


class SplitChoiceDialog(QDialog):
    def __init__(self, count: int, current: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle('確認音檔切割')
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f'已加入 {count} 個音檔。開始轉錄前，要先切割音檔嗎？'))
        self.choice = QComboBox()
        self.choice.addItem('不切割', 0)
        for m in (10, 15, 30, 60): self.choice.addItem(f'每 {m} 分鐘切一段', m)
        self.choice.addItem('自訂分鐘數', -1)
        self.custom = QSpinBox(); self.custom.setRange(1, 180); self.custom.setValue(current if current > 0 else 30)
        self.custom.setSuffix(' 分鐘')
        row = QHBoxLayout(); row.addWidget(self.choice, 1); row.addWidget(self.custom)
        root.addLayout(row)
        note = QLabel('提示：Google Gemini 啟用多人講者或字詞時間戳時，單次音訊最多 30 分鐘；程式也會自動保護切割。')
        note.setWordWrap(True); root.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        idx = self.choice.findData(current)
        if idx >= 0: self.choice.setCurrentIndex(idx)
        self.choice.currentIndexChanged.connect(self._sync)
        self._sync()
    def _sync(self): self.custom.setEnabled(self.choice.currentData() == -1)
    def minutes(self): return self.custom.value() if self.choice.currentData() == -1 else int(self.choice.currentData())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Junba AI Transcriber v2.2')
        self.resize(1080, 820)
        self.worker = None
        self.api_test_worker = None
        self.diag_worker = None
        self.qs = settings()
        tabs = QTabWidget()
        tabs.addTab(self._build_workspace(), '工作區')
        tabs.addTab(self._build_settings(), '設定')
        self.setCentralWidget(tabs)
        self.statusBar().showMessage('就緒')
        self._update_mode_ui()

    def _build_workspace(self):
        w = QWidget(); root = QVBoxLayout(w)
        title = QLabel('Junba AI Transcriber v2.2｜離線 Whisper × Google Gemini')
        title.setStyleSheet('font-size:20px;font-weight:700;padding:6px;'); root.addWidget(title)
        hint = QLabel('可按「加入音檔」一次多選，或直接把多個音檔從檔案總管拖曳到下方清單。')
        hint.setStyleSheet('color:#b8c7d9;'); root.addWidget(hint)

        self.files = AudioListWidget(); self.files.filesDropped.connect(self._add_paths)
        root.addWidget(self.files, 1)
        row = QHBoxLayout()
        for text, fn in [('加入音檔', self.add_files), ('移除選取', self.remove_selected), ('清空', self.files.clear), ('合併音檔', self.merge_selected)]:
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        root.addLayout(row)

        box = QGroupBox('工作流程'); form = QFormLayout(box)
        self.mode = QComboBox(); self.mode.addItems(['離線 Whisper', 'Google Gemini', '混合模式'])
        self.mode.currentTextChanged.connect(self._update_mode_ui)
        self.model = QComboBox(); self.model.addItems(['large-v3', 'medium', 'small', 'base'])
        self.local_model = QLineEdit(self.qs.value('local_model_dir', ''))
        modelrow = QHBoxLayout(); modelrow.addWidget(self.local_model, 1); modelbrowse = QPushButton('本機模型…'); modelbrowse.clicked.connect(self.choose_model_dir); modelrow.addWidget(modelbrowse)
        self.language = QComboBox(); self.language.addItem('自動偵測', 'auto'); self.language.addItem('中文 / 華台混合', 'zh'); self.language.addItem('英文', 'en'); self.language.addItem('日文', 'ja')
        self.split = QSpinBox(); self.split.setRange(0, 180); self.split.setValue(30); self.split.setSuffix(' 分鐘（0=不切割）')
        self.diar = QCheckBox('多人講者（Gemini 音訊模式）'); self.diar.setChecked(True)
        self.timestamps = QCheckBox('字詞時間戳'); self.timestamps.setChecked(True)
        self.smart = QCheckBox('Gemini 智慧逐字稿')
        flags = QHBoxLayout(); flags.addWidget(self.diar); flags.addWidget(self.timestamps); flags.addWidget(self.smart)
        self.privacy = QLabel(''); self.privacy.setWordWrap(True)
        form.addRow('辨識引擎', self.mode); form.addRow('Whisper 模型', self.model); form.addRow('本機模型資料夾', modelrow); form.addRow('語言', self.language); form.addRow('切割', self.split); form.addRow('功能', flags); form.addRow('', self.privacy)
        root.addWidget(box)

        outrow = QHBoxLayout(); self.output = QLineEdit(str(Path.home() / 'Documents' / 'JunbaTranscripts')); btn = QPushButton('選擇輸出位置'); btn.clicked.connect(self.choose_output); outrow.addWidget(self.output, 1); outrow.addWidget(btn); root.addLayout(outrow)
        fmts = QHBoxLayout(); self.f_docx=QCheckBox('Word'); self.f_docx.setChecked(True); self.f_txt=QCheckBox('TXT'); self.f_txt.setChecked(True); self.f_srt=QCheckBox('SRT'); self.f_srt.setChecked(True); self.f_vtt=QCheckBox('VTT')
        for x in (self.f_docx,self.f_txt,self.f_srt,self.f_vtt): fmts.addWidget(x)
        fmts.addStretch(); root.addLayout(fmts)

        self.stage_label = QLabel('目前階段：待命')
        root.addWidget(self.stage_label)
        self.stage_progress = QProgressBar(); self.stage_progress.setRange(0,100); self.stage_progress.setValue(0); self.stage_progress.setFormat('目前階段 %p%')
        self.overall_progress = QProgressBar(); self.overall_progress.setRange(0,100); self.overall_progress.setValue(0); self.overall_progress.setFormat('整體進度 %p%')
        root.addWidget(self.stage_progress); root.addWidget(self.overall_progress)
        self.checkpoint_label = QLabel('進度快取：尚未建立'); self.checkpoint_label.setWordWrap(True); root.addWidget(self.checkpoint_label)

        controls = QHBoxLayout()
        self.start_btn=QPushButton('▶ 開始'); self.pause_btn=QPushButton('⏸ 暫停'); self.resume_btn=QPushButton('▶ 繼續'); self.stop_btn=QPushButton('■ 立即停止')
        self.start_btn.clicked.connect(self.start); self.pause_btn.clicked.connect(self.pause); self.resume_btn.clicked.connect(self.resume); self.stop_btn.clicked.connect(self.stop)
        for b in (self.start_btn,self.pause_btn,self.resume_btn,self.stop_btn): controls.addWidget(b)
        root.addLayout(controls)

        self.logbox = QPlainTextEdit(); self.logbox.setReadOnly(True); self.logbox.setMaximumBlockCount(500); self.logbox.setMaximumHeight(135); self.logbox.setPlaceholderText('執行紀錄會顯示在這裡，方便判斷程式是否仍在運作。')
        root.addWidget(self.logbox)
        return w

    def _build_settings(self):
        w=QWidget(); root=QVBoxLayout(w)
        g=QGroupBox('Google AI Studio / Gemini API'); f=QFormLayout(g)
        self.api_key=QLineEdit(load_api_key()); self.api_key.setEchoMode(QLineEdit.Password)
        show=QCheckBox('顯示 API Key'); show.toggled.connect(lambda on: self.api_key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        save=QPushButton('儲存 API Key'); save.clicked.connect(self.save_key)
        getkey=QPushButton('前往取得 API Key'); getkey.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(API_KEY_URL)))
        self.testkey=QPushButton('測試 API Key'); self.testkey.clicked.connect(self.test_api_key)
        keybuttons=QHBoxLayout(); keybuttons.addWidget(save); keybuttons.addWidget(getkey); keybuttons.addWidget(self.testkey)
        self.api_status=QLabel('尚未測試'); self.api_status.setWordWrap(True)
        f.addRow('Gemini API Key', self.api_key); f.addRow('', show); f.addRow('', keybuttons); f.addRow('連線狀態', self.api_status)
        root.addWidget(g)

        dg=QGroupBox('程式環境檢查'); dl=QVBoxLayout(dg)
        self.diag_btn=QPushButton('執行環境檢查'); self.diag_btn.clicked.connect(self.run_diagnostics)
        self.diag_text=QPlainTextEdit(); self.diag_text.setReadOnly(True); self.diag_text.setMaximumHeight(240)
        dl.addWidget(self.diag_btn); dl.addWidget(self.diag_text); root.addWidget(dg)
        info=QLabel('API Key 儲存在 Windows 認證儲存區，不寫死在 EXE。\nGoogle Gemini 模式會上傳音訊；混合模式只上傳 Whisper 產生的文字；離線 Whisper 不上傳音訊。')
        info.setWordWrap(True); root.addWidget(info); root.addStretch()
        return w

    def _all_files(self):
        return [self.files.item(i).data(Qt.UserRole) or self.files.item(i).text() for i in range(self.files.count())]

    def add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'選擇音檔','','音訊/影片 (*.m4a *.mp3 *.wav *.aac *.flac *.ogg *.aiff *.opus *.mp4 *.webm);;所有檔案 (*.*)')
        self._add_paths(paths)

    def _add_paths(self, paths):
        existing=set(self._all_files()); added=[]
        for p in paths:
            p=str(Path(p))
            if p not in existing and Path(p).suffix.lower() in AUDIO_EXTS:
                dur=audio_duration_seconds(p)
                label=f'{p}   [{dur/60:.1f} 分]' if dur > 0 else p
                item=QListWidgetItem(label); item.setData(Qt.UserRole,p); self.files.addItem(item)
                existing.add(p); added.append(p)
        if added:
            self._append_log(f'已加入 {len(added)} 個音檔。')
            dlg=SplitChoiceDialog(len(added), self.split.value(), self)
            if dlg.exec() == QDialog.Accepted:
                self.split.setValue(dlg.minutes())
                self._append_log('切割設定：' + ('不切割' if dlg.minutes()==0 else f'每 {dlg.minutes()} 分鐘'))

    def remove_selected(self):
        for item in self.files.selectedItems(): self.files.takeItem(self.files.row(item))

    def merge_selected(self):
        selected=[x.data(Qt.UserRole) or x.text() for x in self.files.selectedItems()]
        paths=selected if len(selected)>=2 else self._all_files()
        if len(paths)<2:
            QMessageBox.information(self,'提示','至少加入兩個音檔才能合併。'); return
        out,_=QFileDialog.getSaveFileName(self,'合併輸出',str(Path(self.output.text())/'合併音檔.m4a'),'M4A (*.m4a)')
        if not out: return
        try:
            self.stage_label.setText('目前階段：合併音檔')
            merge_audio(paths,out, progress_cb=self._set_stage_progress)
            QMessageBox.information(self,'完成',f'已合併：\n{out}')
        except Exception as e: QMessageBox.critical(self,'合併失敗',str(e))

    def choose_model_dir(self):
        p=QFileDialog.getExistingDirectory(self,'選擇 faster-whisper 本機模型資料夾',self.local_model.text() or str(Path.cwd()/'models'))
        if p: self.local_model.setText(p); self.qs.setValue('local_model_dir', p)

    def choose_output(self):
        p=QFileDialog.getExistingDirectory(self,'選擇輸出資料夾',self.output.text())
        if p: self.output.setText(p)

    def save_key(self):
        try:
            save_api_key(self.api_key.text()); self.api_status.setText('API Key 已儲存到 Windows 認證儲存區。')
        except Exception as e:
            QMessageBox.critical(self,'儲存失敗',str(e))

    def test_api_key(self):
        key=self.api_key.text().strip()
        if not key:
            QMessageBox.warning(self,'缺少 API Key','請先貼上 Gemini API Key。'); return
        self.testkey.setEnabled(False); self.api_status.setText('測試連線中…')
        self.api_test_worker=ApiKeyTestWorker(key); self.api_test_worker.done.connect(self._api_test_done); self.api_test_worker.start()

    def _api_test_done(self, ok, text):
        self.testkey.setEnabled(True); self.api_status.setText(('✓ ' if ok else '✗ ')+text)

    def run_diagnostics(self):
        self.diag_btn.setEnabled(False); self.diag_text.setPlainText('檢查中…')
        self.diag_worker=DiagnosticsWorker(self.output.text(), self.local_model.text().strip())
        self.diag_worker.done.connect(self._diag_done); self.diag_worker.start()

    def _diag_done(self, ok, text):
        self.diag_btn.setEnabled(True); self.diag_text.setPlainText(text + ('\n\n整體：可開始測試。' if ok else '\n\n整體：有必要元件缺失，請先修正紅叉項目。'))

    def _update_mode_ui(self):
        if not hasattr(self,'mode'): return
        mode=self.mode.currentText()
        is_google=mode=='Google Gemini'
        self.diar.setEnabled(is_google)
        self.smart.setEnabled(is_google)
        if not is_google:
            self.diar.setChecked(False); self.smart.setChecked(False)
        self.model.setEnabled(mode!='Google Gemini'); self.local_model.setEnabled(mode!='Google Gemini')
        if mode=='離線 Whisper': self.privacy.setText('🔒 完全離線：音訊不會上傳。注意：標準版尚未啟用離線多人講者。')
        elif mode=='混合模式': self.privacy.setText('🔀 Whisper 在本機辨識；只把辨識後文字送至 Gemini 整理，音訊不會上傳。')
        else: self.privacy.setText('☁ 線上模式：音訊會上傳至 Google Gemini。可使用多人講者與字詞時間戳。')

    def start(self):
        files=self._all_files()
        if not files: QMessageBox.warning(self,'缺少音檔','請先加入音檔。'); return
        mode=self.mode.currentText(); key=self.api_key.text().strip()
        if mode in ('Google Gemini','混合模式') and not key:
            QMessageBox.warning(self,'缺少 API Key','請到「設定」輸入 Gemini API Key。'); return
        if mode=='Google Gemini' and self.smart.isChecked() and (self.diar.isChecked() or self.timestamps.isChecked()):
            QMessageBox.warning(self,'設定衝突','Gemini 智慧逐字稿不能同時使用多人講者或字詞時間戳。'); return
        formats=[]
        if self.f_docx.isChecked(): formats.append('docx')
        if self.f_txt.isChecked(): formats.append('txt')
        if self.f_srt.isChecked(): formats.append('srt')
        if self.f_vtt.isChecked(): formats.append('vtt')
        if not formats: QMessageBox.warning(self,'缺少輸出格式','請至少選一種輸出格式。'); return
        try:
            Path(self.output.text()).mkdir(parents=True,exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self,'輸出位置無法使用',str(e)); return
        model_arg=self.local_model.text().strip() if self.local_model.text().strip() else self.model.currentText()
        if self.local_model.text().strip() and not Path(self.local_model.text().strip()).is_dir():
            QMessageBox.warning(self,'本機模型路徑錯誤','指定的本機模型資料夾不存在。'); return
        self.qs.setValue('local_model_dir', self.local_model.text().strip())
        self.worker=TranscribeWorker(files,self.output.text(),mode,self.split.value(),model_arg,self.language.currentData(),key,self.diar.isChecked(),self.timestamps.isChecked(),self.smart.isChecked(),formats)
        self.worker.status.connect(self.statusBar().showMessage)
        self.worker.progress.connect(self.overall_progress.setValue)
        self.worker.stage_progress.connect(self._set_stage_progress)
        self.worker.stage_text.connect(lambda t: self.stage_label.setText('目前階段：'+t))
        self.worker.log.connect(self._append_log)
        self.worker.checkpoint.connect(self.checkpoint_label.setText)
        self.worker.file_done.connect(self._file_done)
        self.worker.failed.connect(self._failed)
        self.worker.finished_ok.connect(self._ok)
        self.worker.cancelled.connect(self._cancelled)
        self.worker.finished.connect(self._thread_finished)
        self._set_running(True); self.overall_progress.setValue(0); self.stage_progress.setValue(0); self.worker.start()

    def pause(self):
        if self.worker and self.worker.isRunning(): self.worker.pause(); self._append_log('已要求暫停；會在下一個安全點停住。')
    def resume(self):
        if self.worker and self.worker.isRunning(): self.worker.resume(); self._append_log('繼續處理。')
    def stop(self):
        if self.worker and self.worker.isRunning(): self.worker.stop(); self._append_log('已要求停止；正在等待目前引擎安全返回。')

    def _set_stage_progress(self, pct):
        if pct < 0:
            self.stage_progress.setRange(0,0); self.stage_progress.setFormat('處理中…')
        else:
            if self.stage_progress.minimum()==0 and self.stage_progress.maximum()==0: self.stage_progress.setRange(0,100)
            self.stage_progress.setValue(max(0,min(100,pct))); self.stage_progress.setFormat('目前階段 %p%')

    def _append_log(self, text):
        self.logbox.appendPlainText(text)

    def _set_running(self, running):
        self.start_btn.setEnabled(not running); self.pause_btn.setEnabled(running); self.resume_btn.setEnabled(running); self.stop_btn.setEnabled(running)

    def _file_done(self, text):
        self._append_log('已輸出： '+text.replace('\n',' | ')); self.statusBar().showMessage('檔案輸出完成')
    def _failed(self, text):
        self._append_log('錯誤：'+text); QMessageBox.critical(self,'處理失敗',text)
    def _ok(self):
        self._append_log('所有工作已完成。'); QMessageBox.information(self,'完成','所有工作已完成。')
    def _cancelled(self):
        self._append_log('工作已停止，已完成區段保留，可用相同設定再次開始以讀取快取。')
    def _thread_finished(self):
        self._set_running(False)
        if self.worker:
            self.worker.deleteLater(); self.worker=None

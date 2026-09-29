import sys
from pathlib import Path


def self_test(argv):
    from app.core.diagnostics import environment_report
    out = argv[0] if argv else str(Path.cwd() / 'JunbaAITranscriber_SELFTEST.txt')
    ok, report = environment_report(str(Path(out).parent), '')
    Path(out).write_text(('SELFTEST_OK\n' if ok else 'SELFTEST_FAILED\n') + report, encoding='utf-8')
    return 0 if ok else 2


def main():
    if '--self-test' in sys.argv:
        i = sys.argv.index('--self-test')
        raise SystemExit(self_test(sys.argv[i+1:i+2]))
    from PySide6.QtWidgets import QApplication
    from app.ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName('Junba AI Transcriber')
    app.setOrganizationName('Junba')
    win = MainWindow(); win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

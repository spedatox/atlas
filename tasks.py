"""Run storage/network work off the Qt UI thread, with a modal progress indicator."""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot, Qt
from PySide6.QtWidgets import QProgressDialog


class _Signals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _Worker(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = _Signals()

    def run(self):
        try:
            self.signals.succeeded.emit(self.operation())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class _Task(QObject):
    def __init__(self, parent, title, operation, success, failure):
        super().__init__(parent)
        self.success, self.failure = success, failure
        self.progress = QProgressDialog(title, '', 0, 0, parent)
        self.progress.setCancelButton(None)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.progress.setMinimumDuration(0)
        self.worker = _Worker(operation)
        self.worker.signals.succeeded.connect(self._success)
        self.worker.signals.failed.connect(self._failure)
        self.progress.show()
        QThreadPool.globalInstance().start(self.worker)

    def _close(self):
        self.progress.close()
        self.progress.deleteLater()
        self.deleteLater()

    @Slot(object)
    def _success(self, result):
        self._close()
        self.success(result)

    @Slot(str)
    def _failure(self, message):
        self._close()
        self.failure(message)


def run_task(parent, title, operation, success, failure):
    return _Task(parent, title, operation, success, failure)

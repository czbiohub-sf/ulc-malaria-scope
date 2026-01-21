from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLineEdit


class ClickableLineEdit(QLineEdit):
    gotFocus = pyqtSignal()

    def focusInEvent(self, event):
        self.gotFocus.emit()
        QLineEdit.focusInEvent(self, event)

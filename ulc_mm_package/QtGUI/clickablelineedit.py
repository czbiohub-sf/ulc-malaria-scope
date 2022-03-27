from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLineEdit


class ClickableLineEdit(QLineEdit):
    gotFocus = pyqtSignal()

    def focusInEvent(self, event):
        self.gotFocus.emit()
        QLineEdit.focusInEvent(self, event)
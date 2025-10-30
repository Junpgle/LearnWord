import random, os
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from vocab_model import VocabModel

class ReviewWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("")
        self.setFixedSize(1000,700)
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        btn_row = QHBoxLayout(); btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面"); btn_row.addWidget(self.btn_return); layout.addLayout(btn_row)
        self.word_label = QLabel("", alignment=Qt.AlignCenter); self.word_label.setFont(QFont("MiSans", 26, QFont.Bold)); layout.addWidget(self.word_label)
        know_row = QHBoxLayout(); know_row.addStretch(); self.know_btn = QPushButton("认识"); self.unknow_btn = QPushButton("不认识"); know_row.addWidget(self.know_btn); know_row.addWidget(self.unknow_btn); know_row.addStretch(); layout.addLayout(know_row)
        self.cloze = QLabel("", alignment=Qt.AlignCenter); self.cloze.setFont(QFont("MiSans", 20, QFont.Bold)); layout.addWidget(self.cloze)
        self.input = QLineEdit(); layout.addWidget(self.input)
        self.submit = QPushButton("提交"); layout.addWidget(self.submit)
        self.next_btn = QPushButton("下一词"); self.next_btn.setEnabled(False); layout.addWidget(self.next_btn)
        self.btn_return.clicked.connect(self.close); self.know_btn.clicked.connect(self.on_know); self.unknow_btn.clicked.connect(self.on_unknow); self.submit.clicked.connect(self.on_submit); self.next_btn.clicked.connect(self.next_word)
        self.queue = []
        self.current = None
        self._prepare_and_start()

    def _prepare_and_start(self):
        count = self.model.settings.get("review_count", 15)
        pool = [w for w in self.model.words if True]
        learned_pool = [w for w in pool if w.learned]
        use_pool = learned_pool if learned_pool else pool
        random.shuffle(use_pool)
        self.queue = use_pool[:min(count, len(use_pool))]
        self._show_next()

    def _show_next(self):
        self.next_btn.setEnabled(False)
        if not self.queue:
            QMessageBox.information(self, "完成", "复习完成"); return
        self.current = self.queue.pop(0)
        # start from phase2
        self.word_label.setText(self.current.word); self.cloze.setText(""); self.input.setText("")

    def on_know(self):
        if not self.current: return
        # completing phase2 means stage increments and word moved to tail
        self.current.stage = min(3, self.current.stage + 1)
        self.queue.append(self.current); self.model.save_progress()
        # next word will not be phase3 for this word until it cycles back
        self._show_next()

    def on_unknow(self):
        if not self.current: return
        self.current.stage = 1
        self.current.attempts += 1
        self.queue.append(self.current); self.model.save_progress()
        self._show_next()

    def on_submit(self):
        if not self.current: return
        s = self.input.text().strip()
        if s.lower() == self.current.word.lower():
            QMessageBox.information(self, "正确", "拼写正确"); self.current.learned = True; self.model.save_progress(); self.next_btn.setEnabled(True)
        else:
            QMessageBox.information(self, "错误", f"正确: {self.current.word}"); self.current.stage = 1; self.model.save_progress(); self.next_btn.setEnabled(True)

    def next_word(self):
        self.next_btn.setEnabled(False); self._show_next()

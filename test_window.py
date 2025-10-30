import random, os, csv
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QHBoxLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from vocab_model import VocabModel

class TestWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("")
        self.setFixedSize(1000,700)
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        btn_row = QHBoxLayout(); btn_row.addStretch(); self.btn_return = QPushButton("返回主页面"); btn_row.addWidget(self.btn_return); layout.addLayout(btn_row)
        self.cloze = QLabel("", alignment=Qt.AlignCenter); self.cloze.setFont(QFont("MiSans", 22, QFont.Bold)); layout.addWidget(self.cloze)
        self.input = QLineEdit(); layout.addWidget(self.input)
        row = QHBoxLayout(); self.submit = QPushButton("提交"); self.next_btn = QPushButton("下一题"); self.next_btn.setEnabled(False); row.addWidget(self.submit); row.addWidget(self.next_btn); layout.addLayout(row)
        self.score = QLabel("0 / 0 (0.00%)"); layout.addWidget(self.score)
        self.btn_return.clicked.connect(self.close); self.submit.clicked.connect(self.on_submit); self.next_btn.clicked.connect(self.next_q)
        self.words = []; self._load_words(); self.test_list = []; self.current = None; self.total = 0; self.correct = 0
        self._prepare_and_start()

    def _load_words(self):
        path = os.path.join("data","last_words.csv")
        if not os.path.exists(path):
            path = "words.csv" if os.path.exists("words.csv") else None
        if not path: return
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f); rows = list(reader); start=0
            if rows and any('单词' in c or 'word' in c.lower() for c in rows[0]): start=1
            for row in rows[start:]:
                if not row: continue
                w = row[0].strip(); d = row[2].strip() if len(row)>=3 else (row[1].strip() if len(row)>=2 else ""); wi = type("W",(object,),{})(); wi.word=w; wi.definition=d; self.words.append(wi)

    def _prepare_and_start(self):
        count = self.model.settings.get("test_count", 20)
        pool = self.words.copy()
        if not pool:
            QMessageBox.information(self, "提示", "词库为空"); return
        random.shuffle(pool); self.test_list = pool[:min(count, len(pool))]; self.total = 0; self.correct = 0; self.next_q()

    def next_q(self):
        self.next_btn.setEnabled(False)
        if not self.test_list:
            QMessageBox.information(self, "完成", "测试完成"); return
        self.current = self.test_list.pop(0)
        # show single-line cloze + definition without literal \n
        cloze = self._make_cloze(self.current.word)
        if self.current.definition:
            self.cloze.setText(f"{cloze}    释义: {self.current.definition}")
        else:
            self.cloze.setText(cloze)
        self.input.setText("")

    def on_submit(self):
        if not self.current: return
        s = self.input.text().strip()
        if s == "": QMessageBox.warning(self, "提示", "请输入答案"); return
        self.total += 1
        if s.lower() == self.current.word.lower():
            self.correct += 1; QMessageBox.information(self, "正确", "回答正确"); QTimer.singleShot(1500, self.next_q)
        else:
            QMessageBox.information(self, "错误", f"正确: {self.current.word}"); self.next_btn.setEnabled(True)
        self._update_score()

    def _update_score(self):
        pct = (self.correct/self.total*100) if self.total>0 else 0.0; self.score.setText(f"{self.correct} / {self.total} ({pct:.2f}%)")

    def _make_cloze(self, word):
        chars = list(word); import random as _r; n = max(1, min(len(chars)-1, _r.randint(1, max(1, len(chars)//2)))); idxs = _r.sample(range(len(chars)), n); return ' '.join([('_' if i in idxs else c) for i,c in enumerate(chars)])
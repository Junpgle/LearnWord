import csv
import os
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QHBoxLayout, QSizePolicy
)

from vocab_model import VocabModel


class TestWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.model.load_settings()
        self.setWindowTitle("单词测试模式")
        self.setFixedSize(1000, 700)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 返回按钮布局
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面")
        btn_row.addWidget(self.btn_return)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        # --- 修改点 1: 填空/释义显示区域 ---
        # 使用 AlignmentFlag 修复 PySide6 报错
        self.cloze = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)

        # 使用 Weight.Bold 修复 PySide6 报错
        self.cloze.setFont(QFont("MiSans", 22, QFont.Weight.Bold))

        # ★★★ 关键设置：开启自动换行，解决文字变成省略号的问题 ★★★
        self.cloze.setWordWrap(True)

        # 设置尺寸策略：垂直方向允许被撑大 (使用 Policy 修复报错)
        self.cloze.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout.addWidget(self.cloze)
        # --------------------------------

        # 用户输入框
        self.input = QLineEdit()
        self.input.setObjectName("test_input")
        self.input.setMaximumWidth(600)

        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.input)
        input_row.addStretch()
        layout.addLayout(input_row)

        # 提交和下一题按钮布局
        row = QHBoxLayout()
        row.addStretch(1)

        self.submit = QPushButton("提交")
        self.submit.setObjectName("submit_btn")

        self.next_btn = QPushButton("下一题")
        self.next_btn.setObjectName("next_btn")
        self.next_btn.setEnabled(False)

        row.addWidget(self.submit)
        row.addWidget(self.next_btn)
        row.addStretch(1)
        layout.addLayout(row)

        # --- 修改点 2: 计分板修复 ---
        self.score = QLabel("0 / 0 (0.00%)", alignment=Qt.AlignmentFlag.AlignCenter)
        self.score.setFont(QFont("MiSans", 18, QFont.Weight.Bold))
        layout.addWidget(self.score)

        layout.addStretch(1)

        # 信号连接
        self.btn_return.clicked.connect(self.close)
        self.submit.clicked.connect(self.on_submit)
        self.next_btn.clicked.connect(self.next_q)
        self.input.returnPressed.connect(self.on_submit)

        # 数据初始化
        self.words = []
        self.test_list = []
        self.current = None
        self.total = 0
        self.correct = 0

        self._prepare_and_start()

        # 样式表 (保持不变)
        central.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                margin: 5px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.1);
                transition: background-color 0.3s;
            }
            #submit_btn {
                background-color: #0078d7; 
                color: #ffffff;
            }
            #submit_btn:hover {
                background-color: #005bb5;
            }
            #next_btn {
                background-color: #e8e8e8; 
                color: #333333;
            }
            #next_btn:hover {
                background-color: #d1d1d1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999999;
                box-shadow: none;
            }
            QLineEdit {
                padding: 12px 10px;
                border: 2px solid #ccc;
                border-radius: 8px;
                font-size: 18px;
            }
        """)

    def _prepare_and_start(self):
        count = self.model.settings.get("test_count", 20)
        pool = [w for w in self.model.words if not w.tested]

        if not pool:
            QMessageBox.information(self, "提示", "词库为空或所有单词已测试完毕。")
            return

        random.shuffle(pool)
        self.test_list = pool[:min(count, len(pool))]

        self.total = 0
        self.correct = 0
        self._update_score()
        self.next_q()

    def next_q(self):
        self.next_btn.setEnabled(False)

        if not self.test_list:
            self.cloze.setText(f"🎉 本次测试完成！ 🎉\n" f"得分：{self.correct} / {self.total}")
            self.submit.hide()
            self.next_btn.hide()
            self.input.hide()
            self.score.hide()
            self.current = None
            QTimer.singleShot(3000, self.close)
            return

        self.current = self.test_list.pop(0)
        cloze = self._make_cloze(self.current.word)

        if self.current.definition:
            # 这里的 replace 配合 setWordWrap(True) 就能完美显示多行了
            clean_definition = self.current.definition.replace('\n', ' / ')
            pos = self.current.pos
            self.cloze.setText(f"{cloze}\n\n词性:{pos}.\n释义: {clean_definition}\n")
        else:
            self.cloze.setText(cloze)

        self.input.setText("")
        self.input.setFocus()

    def on_submit(self):
        if not self.current: return

        s = self.input.text().strip()
        if s == "":
            QMessageBox.warning(self, "提示", "请输入答案")
            return

        self.total += 1

        if s.lower() == self.current.word.lower():
            self.correct += 1
            QMessageBox.information(self, "正确", "回答正确！")

            tested_word_str = self.current.word
            model_word = next(
                (w for w in self.model.words if w.word.lower() == tested_word_str.lower()),
                None
            )
            if model_word:
                model_word.tested = True
            self.model.save_progress()

            QTimer.singleShot(600, self.next_q)
        else:
            QMessageBox.information(self, "错误", f"正确答案是: {self.current.word}")
            self.next_btn.setEnabled(True)

        self._update_score()

    def _update_score(self):
        pct = (self.correct / self.total * 100) if self.total > 0 else 0.0
        self.score.setText(f"{self.correct} / {self.total} ({pct:.2f}%)")

    def _make_cloze(self, word):
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))
        idxs = _r.sample(range(len(chars)), n)
        return ' '.join([('_' if i in idxs else c) for i, c in enumerate(chars)])
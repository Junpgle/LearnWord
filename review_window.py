import random, os
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, \
    QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from vocab_model import VocabModel


class ReviewWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("")
        self.setFixedSize(1000, 700)
        central = QWidget();
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 1. 返回按钮
        btn_row = QHBoxLayout();
        btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面");
        btn_row.addWidget(self.btn_return);
        layout.addLayout(btn_row)

        # 2. 第一个伸缩项
        layout.addStretch(1)

        # 3. 主要内容
        self.word_label = QLabel("", alignment=Qt.AlignCenter);
        self.word_label.setFont(QFont("MiSans", 26, QFont.Bold));
        layout.addWidget(self.word_label)

        # --- 第二阶段控件 (认识/不认识) ---
        self.phase2_widget = QWidget()
        know_row = QHBoxLayout(self.phase2_widget)
        know_row.addStretch();
        self.know_btn = QPushButton("认识");
        self.unknow_btn = QPushButton("不认识");
        know_row.addWidget(self.know_btn);
        know_row.addWidget(self.unknow_btn);
        know_row.addStretch()
        layout.addWidget(self.phase2_widget)

        # --- 第三阶段控件 (拼写) ---
        self.phase3_widget = QWidget()
        p3_layout = QVBoxLayout(self.phase3_widget)
        self.cloze = QLabel("", alignment=Qt.AlignCenter);
        self.cloze.setFont(QFont("MiSans", 20, QFont.Bold))
        p3_layout.addWidget(self.cloze)
        self.input = QLineEdit()
        p3_layout.addWidget(self.input)

        submit_row = QHBoxLayout();
        submit_row.addStretch()
        self.submit_btn = QPushButton("提交");
        self.idk_btn = QPushButton("我不会")
        self.submit_btn.setFixedSize(120, 40);
        self.idk_btn.setFixedSize(120, 40)
        submit_row.addWidget(self.submit_btn);
        submit_row.addWidget(self.idk_btn);
        submit_row.addStretch()
        p3_layout.addLayout(submit_row)

        layout.addWidget(self.phase3_widget)

        # 4. 第二个伸缩项
        layout.addStretch(1)

        # --- 连接信号 ---
        self.btn_return.clicked.connect(self.close)
        self.know_btn.clicked.connect(self.on_know);
        self.unknow_btn.clicked.connect(self.on_unknow)
        self.submit_btn.clicked.connect(self.on_submit);
        self.idk_btn.clicked.connect(self.on_idk)  # <-- 修改点

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
        if not self.queue:
            self.word_label.setText("🎉 本次复习完成！ 🎉")
            self.phase2_widget.hide()
            self.phase3_widget.hide()
            # 可添加动画或定时关闭窗口
            QTimer.singleShot(3000, self.close)
            return
        self.current = self.queue.pop(0)
        self.word_label.setText(self.current.word)
        self.phase2_widget.show()
        self.phase3_widget.hide()

    def on_know(self):
        if not self.current: return

        self.phase2_widget.hide()
        self.phase3_widget.show()

        self.word_label.setText(self.current.definition or "[没有释义]")
        self.cloze.setText(self._make_cloze(self.current.word))
        self.input.setText("")

    def on_unknow(self):
        if not self.current: return
        self.current.stage = 1
        self.current.attempts += 1
        self.queue.append(self.current);
        self.model.save_progress()
        self._show_next()

    def on_submit(self):
        if not self.current: return
        s = self.input.text().strip()
        if s.lower() == self.current.word.lower():
            QMessageBox.information(self, "正确", "拼写正确")
            self.current.learned = True
            self.current.stage = min(3, self.current.stage + 1)
            self.model.save_progress()
            QTimer.singleShot(1500, self._show_next)  # <-- 自动前进
        else:
            QMessageBox.information(self, "错误", f"正确: {self.current.word}")
            self.current.stage = 1
            self.queue.append(self.current)  # <-- 添加到队列重复
            self.model.save_progress()
            QTimer.singleShot(200, self._show_next)  # <-- 自动前进

    # *** 修改点：添加 on_idk 方法 ***
    def on_idk(self):
        if not self.current: return
        QMessageBox.information(self, "提示", f"正确: {self.current.word}")
        self.current.stage = 1
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(200, self._show_next)

    def _make_cloze(self, word):
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))
        idxs = _r.sample(range(len(chars)), n)
        return " ".join([("_" if i in idxs else c) for i, c in enumerate(chars)])
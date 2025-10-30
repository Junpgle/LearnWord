import random, os, csv
from collections import deque
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, \
    QMessageBox, QFrame
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from vocab_model import VocabModel, WordItem


class LearnWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("")
        self.setFixedSize(1000, 700)
        central = QWidget();
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 1. 返回按钮（保持在顶部）
        btn_row = QHBoxLayout();
        btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面");
        self.btn_return.setFixedSize(120, 36);
        btn_row.addWidget(self.btn_return)
        layout.addLayout(btn_row)

        # 2. 第一个伸缩项
        layout.addStretch(1)

        # 3. 主要内容
        # display word
        self.word_label = QLabel("", alignment=Qt.AlignCenter);
        self.word_label.setFont(QFont("MiSans", 28, QFont.Bold));
        layout.addWidget(self.word_label)
        # phase frame
        self.phase_frame = QFrame();
        self.phase_layout = QVBoxLayout(self.phase_frame);
        layout.addWidget(self.phase_frame)
        # phase1 options
        opt_row = QHBoxLayout()
        self.opt_buttons = [QPushButton() for _ in range(4)]
        for b in self.opt_buttons:
            b.setFixedHeight(64);
            b.clicked.connect(self.on_choice);
            opt_row.addWidget(b)
        self.phase_layout.addLayout(opt_row)
        # phase2 know/unknow
        know_row = QHBoxLayout();
        know_row.addStretch()
        self.know_btn = QPushButton("认识");
        self.unknow_btn = QPushButton("不认识")
        self.know_btn.setFixedSize(120, 40);
        self.unknow_btn.setFixedSize(120, 40)
        know_row.addWidget(self.know_btn);
        know_row.addWidget(self.unknow_btn);
        know_row.addStretch()
        self.phase_layout.addLayout(know_row)
        self.know_btn.clicked.connect(self.on_know);
        self.unknow_btn.clicked.connect(self.on_unknow)
        # phase3 cloze + input
        self.cloze_label = QLabel("", alignment=Qt.AlignCenter);
        self.cloze_label.setFont(QFont("MiSans", 20, QFont.Bold));
        layout.addWidget(self.cloze_label)
        self.spell_input = QLineEdit();
        self.spell_input.setFixedHeight(36);
        layout.addWidget(self.spell_input)
        submit_row = QHBoxLayout();
        submit_row.addStretch()
        self.submit_btn = QPushButton("提交");
        self.idk_btn = QPushButton("我不会")
        self.submit_btn.setFixedSize(120, 40);
        self.idk_btn.setFixedSize(120, 40)
        submit_row.addWidget(self.submit_btn);
        submit_row.addWidget(self.idk_btn);
        submit_row.addStretch()
        layout.addLayout(submit_row)

        # 4. 第二个伸缩项
        layout.addStretch(1)

        # 5. 信号和启动
        self.submit_btn.clicked.connect(self.on_submit);
        self.idk_btn.clicked.connect(self.on_idk)
        self.queue = deque()
        self.current = None
        self.btn_return.clicked.connect(self.close)
        self._prepare_queue_and_start()

    def _prepare_queue_and_start(self):
        count = self.model.settings.get("learn_count", 10)
        pool = [w for w in self.model.words]
        if not pool:
            QMessageBox.information(self, "提示", "词库为空")
            return
        pool.sort(key=lambda x: x.stage, reverse=True)
        selected = pool[:min(count, len(pool))]
        stages = {}
        for w in selected:
            stages.setdefault(w.stage, []).append(w)
        self.queue = deque()
        for st in sorted(stages.keys(), reverse=True):
            grp = stages[st];
            random.shuffle(grp)
            for w in grp: self.queue.append(w)
        self._show_next()

    def _show_next(self):
        if not self.queue:
            QMessageBox.information(self, "完成", "本次学习完成")
            self._hide_all()
            return
        self.current = self.queue.popleft()
        phase = min(max(1, self.current.stage), 3)
        if phase == 1:
            self._enter_phase1(self.current)
        elif phase == 2:
            self._enter_phase2(self.current)
        else:
            self._enter_phase3(self.current)

    def _hide_all(self):
        for b in self.opt_buttons: b.hide()
        self.know_btn.hide();
        self.unknow_btn.hide();
        self.cloze_label.hide();
        self.spell_input.hide();
        self.submit_btn.hide();
        self.idk_btn.hide()
        self.word_label.setText("")

    def _enter_phase1(self, item):
        self.phase_frame.show()
        for b in self.opt_buttons: b.show()
        self.know_btn.hide();
        self.unknow_btn.hide();
        self.cloze_label.hide();
        self.spell_input.hide();
        self.submit_btn.hide();
        self.idk_btn.hide()
        self.word_label.setText(item.word)
        correct = item.definition or ""
        distract = [w.definition for w in self.model.words if w.word != item.word and w.definition]
        distract = list(dict.fromkeys(distract))
        random.shuffle(distract)
        opts = [correct] + distract[:3]
        while len(opts) < 4: opts.append("")
        random.shuffle(opts)
        for b, t in zip(self.opt_buttons, opts): b.setText(t)

    def _enter_phase2(self, item):
        self.phase_frame.show()
        for b in self.opt_buttons: b.hide()
        self.know_btn.show();
        self.unknow_btn.show()
        self.cloze_label.hide();
        self.spell_input.hide();
        self.submit_btn.hide();
        self.idk_btn.hide()
        self.word_label.setText(item.word)

    def _enter_phase3(self, item):
        self.phase_frame.hide()
        for b in self.opt_buttons: b.hide()
        self.know_btn.hide();
        self.unknow_btn.hide()
        self.cloze_label.show();
        self.spell_input.show();
        self.submit_btn.show();
        self.idk_btn.show()
        self.word_label.setText("拼写：")
        self.cloze_label.setText(self._make_cloze(item.word))
        self.spell_input.setText("")

    def on_choice(self):
        btn = self.sender()
        if not self.current: return
        if btn.text().strip() == (self.current.definition or "").strip():
            self.current.stage = min(3, self.current.stage + 1)
            QMessageBox.information(self, "正确", "回答正确")
        else:
            self.current.stage = max(1, self.current.stage - 1)
            self.current.attempts += 1
            QMessageBox.warning(self, "错误", f"正确释义: {self.current.definition or ''}")
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(200, self._show_next)

    def on_know(self):
        if not self.current: return
        self.current.stage = min(3, self.current.stage + 1)
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(200, self._show_next)

    def on_unknow(self):
        if not self.current: return
        self.current.stage = max(1, self.current.stage - 1)
        self.current.attempts += 1
        self.queue.append(self.current)
        self.model.save_progress()
        size = len(self.queue);
        rotated = 0
        while rotated < size:
            if len(self.queue) == 0: break
            if getattr(self.queue[0], "stage", 1) == 1:
                break
            self.queue.append(self.queue.popleft());
            rotated += 1
        QTimer.singleShot(100, self._show_next)

    # *** 修改点：移除了这里错误的 'pro/learn_window.py' 行 ***

    def on_submit(self):
        if not self.current: return
        s = self.spell_input.text().strip()
        self.current.attempts += 1
        if s.lower() == (self.current.word or "").lower():
            self.current.learned = True
            self.current.stage = min(3, self.current.stage + 0)
            self.queue.append(self.current)
            self.model.save_progress()
            QMessageBox.information(self, "正确", "拼写正确")
            QTimer.singleShot(1500, self._show_next)
        else:
            QMessageBox.information(self, "错误", f"正确: {self.current.word}")
            self.current.learned = False
            self.current.stage = 1
            self.queue.append(self.current)
            self.model.save_progress()
            QTimer.singleShot(200, self._show_next)

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
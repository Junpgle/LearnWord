import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, \
    QMessageBox

from vocab_model import VocabModel  # 导入核心数据模型


class ReviewWindow(QMainWindow):
    """
    复习窗口：实现两阶段复习模式 (识别 -> 拼写)，主要针对 learned=True 的单词，
    目标是更新单词的 reviewed 状态和 stage 进度。
    """

    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("单词复习模式")
        self.setFixedSize(1000, 700)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ✅ 左上角阶段指示器（2个圆点）
        self.stage_row = QHBoxLayout()
        self.stage_row.setSpacing(8)
        self.stage_indicators = []
        for i in range(2):
            dot = QLabel()
            dot.setFixedSize(20, 20)
            dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:transparent;")
            self.stage_row.addWidget(dot)
            self.stage_indicators.append(dot)
        self.stage_row.addStretch()
        layout.addLayout(self.stage_row)

        # 1. 返回按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面")
        self.btn_return.setObjectName("return_btn")
        btn_row.addWidget(self.btn_return)
        layout.addLayout(btn_row)

        # 2. 第一个伸缩项：使内容居中
        layout.addStretch(1)

        # 3. 主要内容：单词/释义 显示区域
        self.word_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.word_label.setFont(QFont("MiSans", 26, QFont.Weight.Bold))
        # **启用自动换行**，防止释义过长显示不全
        self.word_label.setWordWrap(True)
        layout.addWidget(self.word_label)

        # --- 第二阶段控件 (阶段一操作：认识/不认识) ---
        self.phase2_widget = QWidget()
        know_row = QHBoxLayout(self.phase2_widget)

        # 布局开始的伸缩项
        know_row.addStretch()

        self.know_btn = QPushButton("认识")
        self.know_btn.setObjectName("know_btn")
        self.unknow_btn = QPushButton("不认识")
        self.unknow_btn.setObjectName("unknow_btn")

        # ✅ 修复点：在初始化时创建“下一个”按钮，并添加到布局中间
        self.phase2_next_btn = QPushButton("下一个")
        self.phase2_next_btn.setObjectName("next_btn")  # 样式与 submit 相同
        self.phase2_next_btn.hide()  # 默认隐藏
        self.phase2_next_btn.clicked.connect(self.on_phase2_next)

        know_row.addWidget(self.know_btn)
        know_row.addWidget(self.unknow_btn)
        # 将“下一个”按钮添加到 最后一个 Stretch 之前，确保居中
        know_row.addWidget(self.phase2_next_btn)

        # 布局结束的伸缩项
        know_row.addStretch()
        layout.addWidget(self.phase2_widget)

        # --- 第三阶段控件 (阶段二操作：拼写/提交) ---
        self.phase3_widget = QWidget()
        p3_layout = QVBoxLayout(self.phase3_widget)

        # 拼写提示（填空）
        self.cloze = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.cloze.setFont(QFont("MiSans", 20, QFont.Weight.Bold))
        p3_layout.addWidget(self.cloze)

        # 拼写输入框布局
        self.input = QLineEdit()
        self.input.setObjectName("review_input")
        self.input.setMaximumWidth(600)

        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.input)
        input_row.addStretch()
        p3_layout.addLayout(input_row)

        # 提交和不会按钮
        submit_row = QHBoxLayout()
        submit_row.addStretch()
        self.submit_btn = QPushButton("提交")
        self.submit_btn.setObjectName("submit_btn")
        self.idk_btn = QPushButton("我不会")
        self.idk_btn.setObjectName("idk_btn")

        submit_row.addWidget(self.submit_btn)
        submit_row.addWidget(self.idk_btn)
        submit_row.addStretch()
        p3_layout.addLayout(submit_row)

        layout.addWidget(self.phase3_widget)

        # 4. 第二个伸缩项：使内容居中
        layout.addStretch(1)

        # --- 连接信号 ---
        self.btn_return.clicked.connect(self.close)
        self.know_btn.clicked.connect(self.on_know)
        self.unknow_btn.clicked.connect(self.on_unknow)
        self.submit_btn.clicked.connect(self.on_submit)
        self.idk_btn.clicked.connect(self.on_idk)

        # 队列和当前单词初始化
        self.queue = []
        self.current = None
        self._prepare_and_start()

        # ✅ 按钮样式美化
        central.setStyleSheet("""
            /* 通用按钮样式 */
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

            /* 主要/正确动作 (认识, 提交, 下一个) - 蓝色 */
            #know_btn, #submit_btn, #next_btn {
                background-color: #0078d7; 
                color: #ffffff;
            }
            #know_btn:hover, #submit_btn:hover, #next_btn:hover {
                background-color: #005bb5;
            }

            /* 次要/重置动作 (不认识, 我不会) - 红色/警告色 */
            #unknow_btn, #idk_btn {
                background-color: #dc3545; /* 红色 */
                color: #ffffff;
            }
            #unknow_btn:hover, #idk_btn:hover {
                background-color: #c82333;
            }

            /* 返回按钮 */
            #return_btn {
                padding: 8px 16px; 
                background-color: #f0f0f0;
                color: #333333;
                box-shadow: none;
            }
            #return_btn:hover {
                background-color: #e0e0e0;
            }

            /* 禁用状态 */
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999999;
                box-shadow: none;
            }

            /* 输入框样式 */
            QLineEdit {
                padding: 12px 10px;
                border: 2px solid #ccc;
                border-radius: 8px;
                font-size: 18px;
            }
        """)

    def _prepare_and_start(self):
        """准备复习队列：优先选择 learned=True 的单词。"""
        count = self.model.settings.get("review_count", 15)
        pool = self.model.words
        learned_pool = [w for w in pool if w.learned]
        use_pool = learned_pool if learned_pool else pool

        if not use_pool:
            QMessageBox.information(self, "提示", "词库为空。")
            QTimer.singleShot(100, self.close)
            return

        random.shuffle(use_pool)
        self.queue = use_pool[:min(count, len(use_pool))]
        self._show_next()

    def keyPressEvent(self, event):
        """全局处理 Enter 键：阶段一触发“认识”或“下一个”，阶段二触发“提交”"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self.current:
                return

            if self.phase2_widget.isVisible():
                # 特殊处理：如果显示了"下一个"按钮，回车触发下一个
                if self.phase2_next_btn.isVisible():
                    self.on_phase2_next()
                else:
                    self.on_know()
            elif self.phase3_widget.isVisible():
                self.on_submit()
        else:
            super().keyPressEvent(event)

    def _update_stage_indicator(self, phase):
        for i, dot in enumerate(self.stage_indicators, start=1):
            if i <= phase:
                dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:#0078d7;")
            else:
                dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:transparent;")

    def _show_next(self):
        """显示下一个单词，或结束复习。"""
        if not self.queue:
            self.word_label.setText("🎉 本次复习完成！ 🎉")
            self.phase2_widget.hide()
            self.phase3_widget.hide()
            QTimer.singleShot(3000, self.close)
            return

        self.current = self.queue.pop(0)
        self.word_label.setText(self.current.word)

        self.phase2_widget.show()

        # 恢复按钮状态：确保显示认识/不认识，隐藏“下一个”
        self.know_btn.show()
        self.unknow_btn.show()
        self.phase2_next_btn.hide()

        self.phase3_widget.hide()
        self._update_stage_indicator(1)

    def on_know(self):
        """用户点击“认识”：进入阶段二。"""
        if not self.current: return
        self.phase2_widget.hide()
        self.phase3_widget.show()
        self._update_stage_indicator(2)

        self.word_label.setText(f"{self.current.pos}. {self.current.definition}")
        self.cloze.setText(self._make_cloze(self.current.word))
        self.input.setText("")
        self.input.setFocus()

    def on_unknow(self):
        """用户点击“不认识”：显示释义。"""
        if not self.current: return

        # 状态重置/调整
        self.current.stage = 1
        self.current.attempts += 1
        self.queue.append(self.current)
        self.model.save_progress()

        # UI 变更：显示释义
        self.word_label.setText(f"{self.current.word}\n{self.current.pos}. {self.current.definition}")

        # 隐藏 认识/不认识，显示下一个
        self.know_btn.hide()
        self.unknow_btn.hide()
        self.phase2_next_btn.show()

    def on_phase2_next(self):
        """点击不认识后的确认按钮，进入下一个单词"""
        self.phase2_next_btn.hide()
        self._show_next()

    def on_submit(self):
        """用户在阶段二提交拼写答案。"""
        if not self.current: return
        s = self.input.text().strip()

        if s.lower() == self.current.word.lower():
            QMessageBox.information(self, "正确", "拼写正确！")
            self.current.learned = True
            self.current.reviewed = True
            self.current.stage = min(3, self.current.stage + 1)
            self.model.save_progress()
            QTimer.singleShot(200, self._show_next)
        else:
            QMessageBox.information(self, "错误", f"正确答案: {self.current.word}")
            self.current.stage = 1
            self.queue.append(self.current)
            self.model.save_progress()
            QTimer.singleShot(100, self._show_next)

    def on_idk(self):
        """用户点击“我不会”。"""
        if not self.current: return
        QMessageBox.information(self, "提示", f"正确答案是: {self.current.word}")
        self.current.stage = 1
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(200, self._show_next)

    def _make_cloze(self, word):
        """生成填空提示。"""
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))
        idxs = _r.sample(range(len(chars)), n)
        return " ".join([("_" if i in idxs else c) for i, c in enumerate(chars)])

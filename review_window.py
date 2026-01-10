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

        # ✅ 阶段一：增加“我记错了”按钮，仅在点击“认识”后出现
        self.phase2_wrong_btn = QPushButton("我记错了")
        self.phase2_wrong_btn.setObjectName("wrong_btn")
        self.phase2_wrong_btn.hide()
        self.phase2_wrong_btn.clicked.connect(self.on_phase1_wrong)

        # ✅ 修复点：在初始化时创建“下一个”按钮，并添加到布局中间
        self.phase2_next_btn = QPushButton("下一个")
        self.phase2_next_btn.setObjectName("next_btn")
        self.phase2_next_btn.hide()
        self.phase2_next_btn.clicked.connect(self.on_phase2_next)

        know_row.addWidget(self.know_btn)
        know_row.addWidget(self.unknow_btn)
        know_row.addWidget(self.phase2_wrong_btn)
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
        self.queue = []  # 第一阶段队列（识别）
        self.phase2_queue = []  # 第二阶段队列（拼写：仅第一阶段“认识”的单词）
        self.current = None
        self.in_phase2 = False
        self.last_action = None  # 记录第一阶段最后一次操作："know" 或 "unknow"
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

            /* 次要/重置动作 (不认识, 我记错了, 我不会) - 红色/警告色 */
            #unknow_btn, #wrong_btn, #idk_btn {
                background-color: #dc3545; /* 红色 */
                color: #ffffff;
            }
            #unknow_btn:hover, #wrong_btn:hover, #idk_btn:hover {
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
        """准备复习队列：仅抽取 learned=True 且 reviewed=False 的单词；若无则提示无需复习。"""
        count = self.model.settings.get("review_count", 15)
        pool = self.model.words
        to_review_pool = [w for w in pool if getattr(w, "learned", False) and not getattr(w, "reviewed", False)]

        if not to_review_pool:
            QMessageBox.information(self, "提示", "没有单词需要复习。")
            QTimer.singleShot(100, self.close)
            return

        random.shuffle(to_review_pool)
        self.queue = to_review_pool[:min(count, len(to_review_pool))]
        self.phase2_queue = []
        self.in_phase2 = False
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
        """显示下一个条目：先跑完整个第一阶段识别；完成后再进入第二阶段拼写。"""
        # 若在第一阶段
        if not self.in_phase2:
            if not self.queue:
                # 第一阶段结束，进入第二阶段
                if not self.phase2_queue:
                    # 没有任何单词进入第二阶段，直接结束
                    self.word_label.setText("🎉 本次复习完成！ 🎉")
                    self.phase2_widget.hide()
                    self.phase3_widget.hide()
                    QTimer.singleShot(3000, self.close)
                    return
                self.in_phase2 = True
                # 切到第二阶段视图
                self.phase2_widget.hide()
                self.phase3_widget.show()
                self._update_stage_indicator(2)
                # 从第二阶段队列取第一个进入拼写
                self.current = self.phase2_queue.pop(0)
                self.word_label.setText(f"{self.current.pos}. {self.current.definition}")
                self.cloze.setText(self._make_cloze(self.current.word))
                self.input.setText("")
                self.input.setFocus()
                return

            # 继续第一阶段：展示下一个词
            self.current = self.queue.pop(0)
            self.word_label.setText(self.current.word)

            # 第一阶段控件显示
            self.phase2_widget.show()
            self.know_btn.show()
            self.unknow_btn.show()
            self.phase2_wrong_btn.hide()
            self.phase2_next_btn.hide()
            self.phase3_widget.hide()
            self._update_stage_indicator(1)
            return

        # 第二阶段流程
        if not self.phase2_queue and not self.current:
            # 第二阶段无任务
            self.word_label.setText("🎉 本次复习完成！ 🎉")
            self.phase2_widget.hide()
            self.phase3_widget.hide()
            QTimer.singleShot(3000, self.close)
            return

        # 若当前为空（来自 on_phase2_next 或提交后），取下一条
        if not self.current:
            self.current = self.phase2_queue.pop(0)

        # 切换到拼写视图
        self.phase2_widget.hide()
        self.phase3_widget.show()
        self._update_stage_indicator(2)
        self.word_label.setText(f"{self.current.pos}. {self.current.definition}")
        self.cloze.setText(self._make_cloze(self.current.word))
        self.input.setText("")
        self.input.setFocus()

    def on_know(self):
        """第一阶段：用户点击“认识”，先展示释义，然后让用户选择“下一个”或“我记错了”。"""
        if not self.current: return
        self.last_action = "know"

        # 展示释义
        self.word_label.setText(f"{self.current.word}\n{self.current.pos}. {self.current.definition}")

        # 切换按钮：隐藏认识/不认识，显示 下一个 + 我记错了
        self.know_btn.hide()
        self.unknow_btn.hide()
        self.phase2_wrong_btn.show()
        self.phase2_next_btn.show()

        # 保持在第一阶段视图
        self.phase2_widget.show()
        self.phase3_widget.hide()
        self._update_stage_indicator(1)

    def on_unknow(self):
        """第一阶段：用户点击“不认识”，短暂展示释义，然后将该词放队尾，点击“下一个”继续。"""
        if not self.current: return
        self.last_action = "unknow"

        # 状态调整（维持未复习），先不立刻入队尾，等待点击“下一个”后再入队
        self.current.stage = 1
        self.current.attempts += 1

        # 展示释义
        self.word_label.setText(f"{self.current.word}\n{self.current.pos}. {self.current.definition}")

        # 切换按钮：隐藏认识/不认识，仅显示 下一个（不显示我记错了）
        self.know_btn.hide()
        self.unknow_btn.hide()
        self.phase2_wrong_btn.hide()
        self.phase2_next_btn.show()

        self.phase2_widget.show()
        self.phase3_widget.hide()
        self._update_stage_indicator(1)

    def on_phase1_wrong(self):
        """第一阶段：用户在认识后点击“我记错了”，等同于不认识，放队尾。"""
        if not self.current: return
        # 入队尾
        self.queue.append(self.current)
        self.model.save_progress()
        # 重置按钮状态并进入下一项
        self.phase2_wrong_btn.hide()
        self.phase2_next_btn.hide()
        self.current = None
        self._show_next()

    def on_phase2_next(self):
        """第一阶段释义提示后的“下一个”按钮：根据 last_action 处理并进入下一项。"""
        if not self.current: return

        if self.last_action == "know":
            # 认识：加入第二阶段队列
            self.phase2_queue.append(self.current)
        elif self.last_action == "unknow":
            # 不认识：放队尾
            self.queue.append(self.current)
        # 清理并继续
        self.model.save_progress()
        self.phase2_wrong_btn.hide()
        self.phase2_next_btn.hide()
        self.current = None
        self._show_next()

    def _advance_phase2_or_finish(self):
        """第二阶段调度：若队列为空则结束，否则展示下一条。"""
        if not self.phase2_queue:
            self.word_label.setText("🎉 本次复习完成！ 🎉")
            self.phase2_widget.hide()
            self.phase3_widget.hide()
            QTimer.singleShot(3000, self.close)
            return
        self._show_next()

    def on_submit(self):
        """第二阶段：提交拼写答案。正确则标记 reviewed=True；错误则放回队尾继续第二阶段。"""
        if not self.current: return
        s = self.input.text().strip()

        if s.lower() == self.current.word.lower():
            QMessageBox.information(self, "正确", "拼写正确！")
            self.current.learned = True
            self.current.reviewed = True
            self.current.stage = min(3, self.current.stage + 1)
            self.model.save_progress()
            # 清空当前，继续第二阶段下一个
            self.current = None
            QTimer.singleShot(150, self._advance_phase2_or_finish)
        else:
            QMessageBox.information(self, "错误", f"正确答案: {self.current.word}")
            self.current.stage = 1
            # 错误：回到第二阶段队尾
            self.phase2_queue.append(self.current)
            self.model.save_progress()
            self.current = None
            QTimer.singleShot(150, self._advance_phase2_or_finish)

    def on_idk(self):
        """第二阶段：用户点击“我不会”，与错误相同处理。"""
        if not self.current: return
        QMessageBox.information(self, "提示", f"正确答案是: {self.current.word}")
        self.current.stage = 1
        self.phase2_queue.append(self.current)
        self.model.save_progress()
        self.current = None
        QTimer.singleShot(150, self._advance_phase2_or_finish)

    def _make_cloze(self, word):
        """生成填空提示。"""
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))
        idxs = _r.sample(range(len(chars)), n)
        return " ".join([("_" if i in idxs else c) for i, c in enumerate(chars)])

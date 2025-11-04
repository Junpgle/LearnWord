import random, os
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, \
    QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
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
        central = QWidget();
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ✅ 左上角阶段指示器（2个圆点）
        # 用于视觉反馈当前处于识别阶段（1）还是拼写阶段（2）
        self.stage_row = QHBoxLayout()
        self.stage_row.setSpacing(8)
        self.stage_indicators = []
        # 复习模式只有两个阶段：识别 (Stage 1) -> 拼写 (Stage 2)
        for i in range(2):
            dot = QLabel()
            dot.setFixedSize(20, 20)
            dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:transparent;")
            self.stage_row.addWidget(dot)
            self.stage_indicators.append(dot)
        self.stage_row.addStretch()
        layout.addLayout(self.stage_row)

        # 1. 返回按钮
        btn_row = QHBoxLayout();
        btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面");
        self.btn_return.setObjectName("return_btn")  # 设置对象名
        btn_row.addWidget(self.btn_return);
        layout.addLayout(btn_row)

        # 2. 第一个伸缩项：使内容居中
        layout.addStretch(1)

        # 3. 主要内容：单词/释义 显示区域
        self.word_label = QLabel("", alignment=Qt.AlignCenter);
        self.word_label.setFont(QFont("MiSans", 26, QFont.Bold));
        layout.addWidget(self.word_label)

        # --- 第二阶段控件 (阶段一操作：认识/不认识) ---
        self.phase2_widget = QWidget()
        know_row = QHBoxLayout(self.phase2_widget)
        know_row.addStretch();
        self.know_btn = QPushButton("认识");
        self.know_btn.setObjectName("know_btn")  # 设置对象名
        self.unknow_btn = QPushButton("不认识");
        self.unknow_btn.setObjectName("unknow_btn")  # 设置对象名
        know_row.addWidget(self.know_btn);
        know_row.addWidget(self.unknow_btn);
        know_row.addStretch()
        layout.addWidget(self.phase2_widget)

        # --- 第三阶段控件 (阶段二操作：拼写/提交) ---
        self.phase3_widget = QWidget()
        p3_layout = QVBoxLayout(self.phase3_widget)

        # 拼写提示（填空）
        self.cloze = QLabel("", alignment=Qt.AlignCenter);
        self.cloze.setFont(QFont("MiSans", 20, QFont.Bold))
        p3_layout.addWidget(self.cloze)

        # 拼写输入框布局 (修改点 1: 居中和最大宽度)
        self.input = QLineEdit()
        self.input.setObjectName("review_input")  # 设置对象名
        self.input.setMaximumWidth(600)  # 限制最大宽度 (与LearnWindow一致)

        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.input)
        input_row.addStretch()
        p3_layout.addLayout(input_row)

        # 提交和不会按钮
        submit_row = QHBoxLayout();
        submit_row.addStretch()
        self.submit_btn = QPushButton("提交");
        self.submit_btn.setObjectName("submit_btn")  # 设置对象名
        self.idk_btn = QPushButton("我不会")
        self.idk_btn.setObjectName("idk_btn")  # 设置对象名
        # 移除固定的 setFixedSize，通过 QSS padding 控制大小
        submit_row.addWidget(self.submit_btn);
        submit_row.addWidget(self.idk_btn);
        submit_row.addStretch()
        p3_layout.addLayout(submit_row)

        layout.addWidget(self.phase3_widget)

        # 4. 第二个伸缩项：使内容居中
        layout.addStretch(1)

        # --- 连接信号 ---
        self.btn_return.clicked.connect(self.close)
        self.know_btn.clicked.connect(self.on_know);  # 认识 -> 进入阶段二
        self.unknow_btn.clicked.connect(self.on_unknow)  # 不认识 -> 阶段重置，放回队列尾
        self.submit_btn.clicked.connect(self.on_submit);  # 提交拼写答案
        self.idk_btn.clicked.connect(self.on_idk)  # 我不会 -> 放弃拼写，阶段重置，放回队列尾

        # 队列和当前单词初始化
        self.queue = []  # 复习队列，存储 WordItem 对象
        self.current = None  # 当前正在复习的 WordItem
        self._prepare_and_start()  # 准备复习单词并开始

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

            /* 主要/正确动作 (认识, 提交) - 蓝色 */
            #know_btn, #submit_btn {
                background-color: #0078d7; 
                color: #ffffff;
            }
            #know_btn:hover, #submit_btn:hover {
                background-color: #005bb5;
            }

            /* 次要/重置动作 (不认识, 我不会) - 红色/警告色，表示需要重学或重做 */
            #unknow_btn, #idk_btn {
                background-color: #dc3545; /* 红色 */
                color: #ffffff;
            }
            #unknow_btn:hover, #idk_btn:hover {
                background-color: #c82333;
            }

            /* 返回按钮 (默认样式) */
            #return_btn {
                padding: 8px 16px; /* 稍微小一点 */
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

            /* 输入框样式 (修改点 2: 统一 padding) */
            QLineEdit {
                padding: 12px 10px; /* 统一 LearnWindow 的大内边距 */
                border: 2px solid #ccc;
                border-radius: 8px;
                font-size: 18px;
            }
        """)

    def _prepare_and_start(self):
        """
        准备复习队列：优先选择 learned=True 的单词，数量由设置决定。
        """
        count = self.model.settings.get("review_count", 15)
        # 过滤出所有单词
        pool = self.model.words  # 直接使用模型的 words 列表
        # 优先复习已学过的单词
        learned_pool = [w for w in pool if w.learned]

        # 如果有已学单词，则复习已学单词；否则，复习整个词库
        use_pool = learned_pool if learned_pool else pool

        if not use_pool:
            QMessageBox.information(self, "提示", "词库为空。")
            QTimer.singleShot(100, self.close)
            return

        random.shuffle(use_pool)
        # 截取设置的复习数量
        self.queue = use_pool[:min(count, len(use_pool))]
        self._show_next()

    def _update_stage_indicator(self, phase):
        """
        更新复习阶段指示灯。
        :param phase: 当前阶段 (1 或 2)
        """
        # i 从 1 开始，对应 phase 1, 2...
        for i, dot in enumerate(self.stage_indicators, start=1):
            if i <= phase:
                # 蓝色表示激活
                dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:#0078d7;")
            else:
                # 透明表示未激活
                dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:transparent;")

    def _show_next(self):
        """
        显示下一个单词，或结束复习。
        """
        if not self.queue:
            self.word_label.setText("🎉 本次复习完成！ 🎉")
            self.phase2_widget.hide()
            self.phase3_widget.hide()
            # 3 秒后自动关闭窗口
            QTimer.singleShot(3000, self.close)
            return

        # 弹出下一个单词，进入阶段一：识别
        self.current = self.queue.pop(0)
        self.word_label.setText(self.current.word)

        # 显示阶段一的控件
        self.phase2_widget.show()
        self.phase3_widget.hide()

        self._update_stage_indicator(1)  # 阶段指示灯设为 1

    def on_know(self):
        """
        用户点击“认识”：进入阶段二（拼写/回忆）。
        """
        if not self.current: return

        self.phase2_widget.hide()
        self.phase3_widget.show()
        self._update_stage_indicator(2)  # 阶段指示灯设为 2

        # 阶段二显示释义和填空提示
        self.word_label.setText(self.current.definition or "[没有释义]")
        self.cloze.setText(self._make_cloze(self.current.word))
        self.input.setText("")
        self.input.setFocus()

    def on_unknow(self):
        """
        用户点击“不认识”：复习失败，将单词重新放回队列尾部，等待下一轮复习。
        """
        if not self.current: return

        # 状态重置/调整：让它在下一轮复习中重新开始
        self.current.stage = 1
        self.current.attempts += 1  # 可用于统计

        # 放回队列尾部
        self.queue.append(self.current);
        self.model.save_progress()  # 保存状态变化

        self._show_next()

    def on_submit(self):
        """
        用户在阶段二提交拼写答案。
        """
        if not self.current: return
        s = self.input.text().strip()

        if s.lower() == self.current.word.lower():
            # 拼写正确
            QMessageBox.information(self, "正确", "拼写正确！")

            # 更新状态：标记为已复习，并确保 learned 状态 (尽管通常从 learned pool 来)
            self.current.learned = True
            self.current.reviewed = True  # ✅ 标记为已成功复习

            # 阶段可以向上提升，最高到 3 (stage=3 通常表示已完成所有学习/测试步骤)
            self.current.stage = min(3, self.current.stage + 1)

            self.model.save_progress()
            QTimer.singleShot(200, self._show_next)  # 自动前进
        else:
            # 拼写错误
            QMessageBox.information(self, "错误", f"正确答案: {self.current.word}")

            # 状态重置：将单词阶段重置为 1，放回队列重新开始
            self.current.stage = 1
            self.queue.append(self.current)

            self.model.save_progress()
            QTimer.singleShot(100, self._show_next)  # 自动前进

    def on_idk(self):
        """
        用户点击“我不会”：相当于拼写失败，重置状态并放回队列。
        """
        if not self.current: return

        # 显示正确答案
        QMessageBox.information(self, "提示", f"正确答案是: {self.current.word}")

        # 状态重置：重置阶段，放回队列
        self.current.stage = 1
        self.queue.append(self.current)

        self.model.save_progress()
        QTimer.singleShot(200, self._show_next)

    def _make_cloze(self, word):
        """
        生成填空提示，随机将单词的部分字母替换为下划线。
        - 至少替换 1 个字母。
        - 最多替换单词长度的一半。
        """
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""

        # 随机确定要替换的字母数量 n
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))

        # 随机选择要替换的字母索引
        idxs = _r.sample(range(len(chars)), n)

        # 生成填空字符串，用空格分隔字母和下划线
        return " ".join([("_" if i in idxs else c) for i, c in enumerate(chars)])

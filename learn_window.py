import random, os, csv
from collections import deque
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, \
    QMessageBox, QFrame, QGridLayout  # 导入 QGridLayout
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor  # 导入 QPalette 和 QColor

from vocab_model import VocabModel


class LearnWindow(QMainWindow):
    """
    单词学习窗口，实现了三阶段学习法：
    阶段1: 词义选择题 (Phase 1)
    阶段2: 认识/不认识自测 (Phase 2)
    阶段3: 拼写填空 (Phase 3)
    """

    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.model.load_settings()
        self.setWindowTitle("单词学习")
        self.setFixedSize(1000, 700)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- 顶部区域 ---

        # 左上角阶段指示器布局
        self.stage_row = QHBoxLayout()
        self.stage_row.setSpacing(8)
        self.stage_indicators = []
        # 创建 3 个圆形指示灯，代表 3 个学习阶段
        for i in range(3):
            dot = QLabel()
            dot.setFixedSize(20, 20)
            dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:transparent;")
            self.stage_row.addWidget(dot)
            self.stage_indicators.append(dot)
        self.stage_row.addStretch()  # 将指示灯推到左侧
        layout.addLayout(self.stage_row)

        # 返回按钮（保持在顶部右侧）
        btn_row = QHBoxLayout()
        btn_row.addStretch()  # 将按钮推到右侧
        self.btn_return = QPushButton("返回主页面")
        self.btn_return.setObjectName("return_btn")  # 设置对象名
        btn_row.addWidget(self.btn_return)
        layout.addLayout(btn_row)

        # --- 中央主要内容区 ---

        # 1. 第一个垂直弹簧：将内容从顶部向下推
        layout.addStretch(1)

        # 单词显示标签 - 用于阶段 1/2 的单词或阶段 3 的释义提示
        self.word_label = QLabel("", alignment=Qt.AlignCenter)
        self.word_label.setFont(QFont("MiSans", 28, QFont.Bold))
        # **启用自动换行**
        self.word_label.setWordWrap(True)
        layout.addWidget(self.word_label)

        # 阶段内容框架：用于切换显示不同阶段的控件
        self.phase_frame = QFrame()
        self.phase_layout = QVBoxLayout(self.phase_frame)
        layout.addWidget(self.phase_frame)

        # 阶段 1: 词义选择题布局 (四选一)
        # **使用 QGridLayout 替代 QHBoxLayout 实现 2x2 布局**
        self.opt_grid = QGridLayout()
        self.opt_buttons = [QPushButton() for _ in range(4)]

        # 2x2 布局设置
        for i, b in enumerate(self.opt_buttons):
            b.setObjectName("choice_btn")  # 设置对象名
            b.setFixedHeight(80)  # 增加高度以容纳多行文字
            # **删除 b.setWordWrap(True) 这行代码**
            # b.setWordWrap(True) # <- 移除这一行!

            # 使用 CSS 替代 setWordWrap 来间接控制换行
            b.setStyleSheet(
                "text-align: center; white-space: normal;"  # 关键：设置 white-space: normal
            )

            b.setMinimumWidth(300)
            b.clicked.connect(self.on_choice)  # 绑定选择点击事件
            # 将按钮依次放置在 0,0 0,1 1,0 1,1
            row = i // 2
            col = i % 2
            self.opt_grid.addWidget(b, row, col)

        # 居中对齐网格布局
        self.opt_grid.setAlignment(Qt.AlignCenter)
        self.phase_layout.addLayout(self.opt_grid)
        self.phase_layout.setAlignment(self.opt_grid, Qt.AlignCenter)

        # 阶段 2: 认识/不认识按钮布局
        know_row = QHBoxLayout()
        know_row.addStretch()
        self.know_btn = QPushButton("认识")
        self.know_btn.setObjectName("know_btn")  # 设置对象名
        self.unknow_btn = QPushButton("不认识")
        self.unknow_btn.setObjectName("unknow_btn")  # 设置对象名
        know_row.addWidget(self.know_btn)
        know_row.addWidget(self.unknow_btn)
        know_row.addStretch()
        self.phase_layout.addLayout(know_row)
        # 注意：这里的 connect 会在 _enter_phase2 中被动态覆盖
        self.know_btn.clicked.connect(self.on_know)
        self.unknow_btn.clicked.connect(self.on_unknow)

        # 阶段 3: 拼写填空内容（直接添加到主布局，位于 phase_frame 之外）
        self.cloze_label = QLabel("", alignment=Qt.AlignCenter)
        self.cloze_label.setFont(QFont("MiSans", 20, QFont.Bold))
        # **启用自动换行**
        self.cloze_label.setWordWrap(True)
        layout.addWidget(self.cloze_label)

        # 输入框居中和宽度限制
        self.spell_input = QLineEdit()
        # self.spell_input.setFixedHeight(36) # 移除固定高度设置
        self.spell_input.setMaximumWidth(600)  # 限制最大宽度，使其居中后视觉更舒适

        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.spell_input)
        input_row.addStretch()
        layout.addLayout(input_row)  # 将居中布局添加到主布局

        # 阶段 3: 提交/我不会 按钮布局
        submit_row = QHBoxLayout()
        submit_row.addStretch()
        self.submit_btn = QPushButton("提交")
        self.submit_btn.setObjectName("submit_btn")  # 设置对象名
        self.idk_btn = QPushButton("我不会")
        self.idk_btn.setObjectName("idk_btn")  # 设置对象名
        submit_row.addWidget(self.submit_btn)
        submit_row.addWidget(self.idk_btn)
        submit_row.addStretch()
        layout.addLayout(submit_row)

        # 2. 第二个垂直弹簧：将内容从底部向上推，实现内容居中效果
        layout.addStretch(1)

        # --- 状态与连接 ---

        # 信号连接
        self.submit_btn.clicked.connect(self.on_submit)
        self.idk_btn.clicked.connect(self.on_idk)
        self.btn_return.clicked.connect(self.close)

        # 学习队列和当前单词状态
        self.queue = deque()  # 存储待学习单词的队列
        self.current = None  # 当前正在学习的单词对象

        # 准备队列并开始学习
        self._prepare_queue_and_start()

        # 按钮样式美化
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
                min-width: 100px; /* 确保最小宽度 */
            }

            /* **重点：阶段 1 选择题按钮样式，确保文本自动换行** */
            #choice_btn {
                text-align: center; 
                background-color: #0078d7; 
                color: #ffffff;
                /* 必须设置足够大的最小高度，让文字换行 */
                min-height: 50px; 
            }
            #choice_btn:hover {
                background-color: #005bb5;
            }

            /* 主要/积极动作 (认识, 提交, 下一个) - 蓝色 */
            #know_btn, #submit_btn, #next_btn {
                background-color: #0078d7; 
                color: #ffffff;
            }
            #know_btn:hover, #submit_btn:hover, #next_btn:hover {
                background-color: #005bb5;
            }

            /* 次要/重置动作 (不认识, 我不会, 我记错了) - 红色/警告色 */
            #unknow_btn, #idk_btn, #wrong_btn {
                background-color: #dc3545; /* 红色 */
                color: #ffffff;
            }
            #unknow_btn:hover, #idk_btn:hover, #wrong_btn:hover {
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

            /* 输入框样式 */
            QLineEdit {
                padding: 12px 10px; /* 增加垂直 padding 确保文字显示完整 */
                border: 2px solid #ccc;
                border-radius: 8px;
                font-size: 18px;
            }
        """)

    def _prepare_queue_and_start(self):
        """准备学习队列，根据学习阶段和设置的数量限制来筛选单词。"""
        # 筛选所有未学完的单词
        all_unlearned = [w for w in self.model.words if not w.learned]

        # 获取设置中定义的本次学习单词数量限制
        count = self.model.settings.get("learn_count", 10)

        pool = [w for w in self.model.words]
        if not pool:
            QMessageBox.information(self, "提示", "词库为空")
            return

        # 根据 stage 阶段降序排序，确保高阶段单词优先被选中
        pool.sort(key=lambda x: x.stage, reverse=True)

        # 从未学完的单词中随机选择本次要学的数量
        selected = random.sample(all_unlearned, min(count, len(all_unlearned)))

        # 按阶段分组 (stages = {1: [w1, w2], 2: [w3], ...})
        stages = {}
        for w in selected:
            stages.setdefault(w.stage, []).append(w)

        # 重新构建队列：按阶段升序（从低阶段开始）加入队列，并在阶段内随机打乱
        self.queue = deque()
        for st in sorted(stages.keys(), reverse=False):  # 注意：这里应是升序 (reverse=False) 确保从 Stage 1 开始学
            grp = stages[st]
            random.shuffle(grp)
            for w in grp: self.queue.append(w)

        self._show_next()

    def _show_next(self):
        """显示下一个单词的当前学习阶段界面。"""
        if not self.queue:
            # 队列为空，学习结束
            self._hide_all()
            self.word_label.setText("🎉 本次学习完成！ 🎉")
            # 3秒后自动关闭窗口
            QTimer.singleShot(3000, self.close)
            return

        self.current = self.queue.popleft()  # 取出队列头部的单词

        # 确定当前单词应该进入的阶段 (确保 stage 在 1 到 3 之间)
        phase = min(max(1, self.current.stage), 3)
        self._update_stage_indicator(phase)  # 更新阶段指示灯

        # 根据阶段进入不同的界面
        if phase == 1:
            self._enter_phase1(self.current)
        elif phase == 2:
            self._enter_phase2(self.current)
        else:
            self._enter_phase3(self.current)

    def _hide_all(self):
        """隐藏所有阶段相关的控件，用于学习结束或切换阶段时的清理。"""
        for b in self.opt_buttons: b.hide()
        self.know_btn.hide()
        self.unknow_btn.hide()
        self.cloze_label.hide()
        self.spell_input.hide()  # 隐藏输入框
        self.submit_btn.hide()
        self.idk_btn.hide()
        self.word_label.setText("")
        # 隐藏动态按钮，如果它们存在
        if hasattr(self, 'next_btn'): self.next_btn.hide()
        if hasattr(self, 'wrong_btn'): self.wrong_btn.hide()

    def _update_stage_indicator(self, phase):
        """更新左上角阶段指示灯的颜色。"""
        for i, dot in enumerate(self.stage_indicators, start=1):
            if i <= phase:
                # 当前或已完成的阶段点亮
                dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:#0078d7;")
            else:
                # 未进行的阶段保持透明
                dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:transparent;")

    def _enter_phase1(self, item):
        """进入阶段 1：词义选择题。"""
        self._hide_all()  # 隐藏所有，再显示需要的
        self.phase_frame.show()

        # 显示阶段 1 控件
        for b in self.opt_buttons: b.show()
        self.word_label.setText(item.word)

        # 准备选项
        correct = item.definition or ""
        # 筛选 3 个干扰项 (确保不与当前单词重复，且有释义)
        distract = [w.definition for w in self.model.words if w.word != item.word and w.definition]
        distract = list(dict.fromkeys(distract))  # 去重
        random.shuffle(distract)

        opts = [correct] + distract[:3]
        while len(opts) < 4: opts.append("")  # 确保选项数量为 4
        random.shuffle(opts)

        # 设置按钮文本
        for b, t in zip(self.opt_buttons, opts): b.setText(t)

    def _enter_phase2(self, item):
        """进入阶段 2：认识/不认识自测。"""
        self._hide_all()  # 隐藏所有，再显示需要的
        self.phase_frame.show()

        # 确保隐藏阶段 1 和 3 的控件
        for b in self.opt_buttons: b.hide()
        self.cloze_label.hide()
        self.spell_input.hide()
        self.submit_btn.hide()
        self.idk_btn.hide()

        # 显示认识/不认识按钮
        self.know_btn.show()
        self.unknow_btn.show()

        # 核心逻辑：解绑 on_know/on_unknow，绑定到 _phase2_handle
        try:
            self.know_btn.clicked.disconnect()
            self.unknow_btn.clicked.disconnect()
        except:  # 首次运行或未绑定时会抛异常，忽略
            pass

        # 绑定点击事件：点击后进入 _phase2_handle 流程
        self.know_btn.clicked.connect(lambda checked=False, i=item: self._phase2_handle(i))
        self.unknow_btn.clicked.connect(lambda checked=False, i=item: self._phase2_handle(i))

        self.word_label.setText(item.word)  # 仅显示单词

    def _phase2_handle(self, item):
        """处理阶段 2 首次点击（认识/不认识）后的界面切换。"""
        # 隐藏原有按钮
        self.know_btn.hide()
        self.unknow_btn.hide()

        # **修改：确保 word_label 文本显示正确且自动换行已设置**
        self.word_label.setText(f"{item.word} : {item.definition or '[无释义]'}")
        self.word_label.setWordWrap(True)  # 再次确保换行开启

        # 创建或显示下一步/我记错了按钮 (用于处理结果)
        if not hasattr(self, 'next_btn'):
            # 首次创建按钮并添加到 phase_layout
            self.next_btn = QPushButton("下一个")  # 相当于“我答对了，进入下一阶段”
            self.next_btn.setObjectName("next_btn")  # 设置对象名
            self.wrong_btn = QPushButton("我记错了")  # 相当于“我答错了，退回阶段 1”
            self.wrong_btn.setObjectName("wrong_btn")  # 设置对象名
            # 移除 setFixedSize，让 QSS padding 控制大小

            self.phase2_btn_row = QHBoxLayout()
            self.phase2_btn_row.addStretch()
            self.phase2_btn_row.addWidget(self.next_btn)
            self.phase2_btn_row.addWidget(self.wrong_btn)
            self.phase2_btn_row.addStretch()
            self.phase_layout.addLayout(self.phase2_btn_row)

            # 绑定点击事件，处理后续逻辑
            self.next_btn.clicked.connect(self._phase2_next)
            self.wrong_btn.clicked.connect(lambda checked=False, i=item: self._phase2_wrong(i))
        else:
            # 非首次，只需显示
            self.next_btn.show()
            self.wrong_btn.show()

    def _phase2_next(self):
        """处理阶段 2 的“下一个”按钮点击：进入下一阶段。"""
        self.next_btn.hide()
        self.wrong_btn.hide()
        if self.current:
            # 成功进入下一阶段 (Stage + 1，但不超过 3)
            self.current.stage = min(3, self.current.stage + 1)
            self.queue.append(self.current)  # 重新加入队列
            self.model.save_progress()
        self._show_next()

    def _phase2_wrong(self, item):
        """处理阶段 2 的“我记错了”按钮点击：退回阶段 1。"""
        # 答错：降级回第一阶段
        item.stage = 1
        item.attempts += 1
        self.queue.append(item)
        self.model.save_progress()
        self.next_btn.hide()
        self.wrong_btn.hide()
        self._show_next()

    def _enter_phase3(self, item):
        """进入阶段 3：拼写填空。"""
        self._hide_all()  # 隐藏所有，再显示需要的
        self.phase_frame.hide()  # 隐藏阶段 1/2 的框架

        # 显示阶段 3 控件
        self.cloze_label.show()
        self.spell_input.show()
        self.submit_btn.show()
        self.idk_btn.show()

        # word_label 显示释义作为提示
        # **修改：确保 word_label 文本显示正确且自动换行已设置**
        self.word_label.setText(f"拼写：{item.definition or '[无释义]'}")
        self.word_label.setWordWrap(True)  # 再次确保换行开启

        # cloez_label 显示带下划线的单词（提示）
        self.cloze_label.setText(self._make_cloze(item.word))
        self.cloze_label.setWordWrap(True)  # 再次确保换行开启

        self.spell_input.setText("")  # 清空输入框

    def on_choice(self):
        """处理阶段 1 的选择题答案提交。"""
        btn = self.sender()  # 获取触发事件的按钮
        if not self.current: return

        # 检查答案是否正确
        if btn.text().strip() == (self.current.definition or "").strip():
            self.current.stage = min(3, self.current.stage + 1)  # 答对：阶段 +1
            QMessageBox.information(self, "正确", "回答正确")
        else:
            self.current.stage = max(1, self.current.stage - 1)  # 答错：阶段 -1 (最低到 1)
            self.current.attempts += 1
            QMessageBox.warning(self, "错误", f"正确释义: {self.current.definition or ''}")

        self.queue.append(self.current)  # 重新加入队列
        self.model.save_progress()
        QTimer.singleShot(100, self._show_next)  # 延迟显示下一题

    def on_know(self):
        """处理阶段 2 首次点击“认识”按钮 (在 _enter_phase2 绑定前)。"""
        if not self.current: return
        # 默认的 on_know/on_unknow 只是处理阶段变化，并重新加入队列
        self.current.stage = min(3, self.current.stage + 1)
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(100, self._show_next)

    def on_unknow(self):
        """处理阶段 2 首次点击“不认识”按钮 (在 _enter_phase2 绑定前)。"""
        if not self.current: return
        self.current.stage = max(1, self.current.stage - 1)
        self.current.attempts += 1
        self.queue.append(self.current)
        self.model.save_progress()

        # 将 Stage 1 的单词推到队列末尾，以便先学习 Stage 2/3 的单词
        size = len(self.queue)
        rotated = 0
        while rotated < size:
            if len(self.queue) == 0: break
            if getattr(self.queue[0], "stage", 1) == 1:
                break
            self.queue.append(self.queue.popleft())
            rotated += 1

        QTimer.singleShot(100, self._show_next)

    def on_submit(self):
        """处理阶段 3 的拼写提交。"""
        if not self.current: return
        s = self.spell_input.text().strip()
        self.current.attempts += 1

        # 检查拼写是否正确（不区分大小写）
        if s.lower() == (self.current.word or "").lower():
            self.current.learned = True  # 拼写正确，标记为已学完
            self.current.stage = min(3, self.current.stage + 0)  # 保持在最高阶段
            self.model.save_progress()
            QMessageBox.information(self, "正确", "拼写正确")
            QTimer.singleShot(200, self._show_next)
        else:
            QMessageBox.information(self, "错误", f"正确: {self.current.word}")
            self.current.learned = False
            self.current.stage = 1  # 拼写错误，退回阶段 1
            self.queue.append(self.current)
            self.model.save_progress()
            QTimer.singleShot(100, self._show_next)

    def on_idk(self):
        """处理阶段 3 的“我不会”按钮点击。"""
        if not self.current: return
        QMessageBox.information(self, "提示", f"正确: {self.current.word}")
        self.current.stage = 1  # 退回阶段 1
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(200, self._show_next)

    def _make_cloze(self, word):
        """生成带下划线的填空提示。"""
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""

        # 随机选择要隐藏的字母数量 (最少 1 个，最多一半)
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))

        # 随机选择 n 个要隐藏的字母的索引
        idxs = _r.sample(range(len(chars)), n)

        # 生成带下划线的字符串
        return " ".join([("_" if i in idxs else c) for i, c in enumerate(chars)])
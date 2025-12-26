import os
import json
import requests
import datetime
import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QSpinBox, QTextEdit, QGroupBox,
                               QFileDialog, QMessageBox, QInputDialog, QDialog)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QMovie

from vocab_model import VocabModel

# ★★★ 样式常量 (减少代码重复) ★★★
BTN_STYLE = """
    QPushButton {
        background-color: #0078d7;
        color: white;
        border: none;
        border-radius: 8px;
    }
    QPushButton:hover {
        background-color: #339af0;
    }
"""

GROUP_BOX_STYLE = "QGroupBox{border:1px solid #ccc;border-radius:12px;padding:10px;}"

PROGRESS_BAR_STYLE = """
    QProgressBar {
        border: 1px solid #aaa;
        border-radius: 10px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: %s;
        border-radius: 10px;
    }
"""


def get_resource_path(relative_path):
    """
    获取资源的绝对路径。
    """
    # 使用 getattr 避免静态检查工具报错 "Cannot find reference '_MEIPASS'"
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径处理
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_path = os.getcwd()

    full_path = os.path.join(base_path, relative_path)

    # 如果在 _MEIPASS 找不到，尝试在 exe 旁边找 (用于外部放置的资源)
    if getattr(sys, 'frozen', False) and not os.path.exists(full_path):
        base_path_exe = os.path.dirname(sys.executable)
        full_path_exe = os.path.join(base_path_exe, relative_path)
        if os.path.exists(full_path_exe):
            return full_path_exe

    return full_path


class DownloadWorker(QThread):
    """后台下载线程，支持进度条显示"""
    finished = Signal(bool, str, str)  # 信号：成功与否, 内容或错误信息, 文件名
    progress_updated = Signal(int)  # 新增信号：当前进度百分比 (0-100)

    def __init__(self, url, filename):
        super().__init__()
        self.url = url
        self.filename = filename
        self._is_running = True

    def stop(self):
        """停止下载"""
        self._is_running = False

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=15)
            response.raise_for_status()

            total_length = response.headers.get('content-length')
            content = ""

            if total_length is None:
                response.encoding = 'utf-8'
                self.progress_updated.emit(50)
                content = response.text
                self.progress_updated.emit(100)
            else:
                dl = 0
                total_length = int(total_length)
                content_bytes = bytearray()

                for data in response.iter_content(chunk_size=4096):
                    if not self._is_running:
                        return

                    dl += len(data)
                    content_bytes.extend(data)

                    percent = min(100, int(100 * dl / total_length))
                    self.progress_updated.emit(percent)

                content = content_bytes.decode('utf-8')

            if self._is_running:
                self.finished.emit(True, content, self.filename)

        except Exception as e:
            if self._is_running:
                self.finished.emit(False, str(e), self.filename)


class DownloadProgressDialog(QDialog):
    canceled = Signal()

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(320, 350)

        # PySide6 Enum 修复
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { color: #333333; background-color: transparent; }
        """)

        layout = QVBoxLayout(self)

        # 1. 动画显示区域
        self.animation_label = QLabel()
        self.animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # PySide6 Enum
        self.animation_label.setMinimumHeight(200)

        gif_path = get_resource_path(os.path.join("Animation", "download.gif"))

        if os.path.exists(gif_path):
            self.movie = QMovie(gif_path)
            self.movie.setScaledSize(QSize(200, 200))
            self.animation_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.animation_label.setText("⬇️")
            font = QFont("Segoe UI Emoji", 80)
            self.animation_label.setFont(font)
            # print(f"未找到动画文件: {gif_path}") 调试用

        layout.addWidget(self.animation_label, 1)

        # 2. 状态文字
        self.status_label = QLabel("准备下载...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # PySide6 Enum
        self.status_label.setFont(QFont("MiSans", 10))
        layout.addWidget(self.status_label)

        # 3. 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e0e0e0;
                background-color: #f5f5f5;
                border-radius: 5px;
                text-align: center;
                height: 15px;
                color: #333333;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 4. 取消按钮
        self.cancel_btn = QPushButton("取消下载")
        self.cancel_btn.setStyleSheet("""
            QPushButton { 
                background-color: #f0f0f0; 
                border: 1px solid #ccc; 
                border-radius: 5px; 
                padding: 6px; 
                color: #333333;
            }
            QPushButton:hover { background-color: #e0e0e0; }
            QPushButton:pressed { background-color: #d0d0d0; }
        """)
        self.cancel_btn.clicked.connect(self.on_cancel)
        layout.addWidget(self.cancel_btn)

    def setValue(self, val):
        self.progress_bar.setValue(val)
        self.status_label.setText(f"正在下载资源... {val}%")

    def on_cancel(self):
        self.canceled.emit()
        self.close()


class SettingWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("设置与进度管理")
        self.setFixedSize(1000, 700)

        # 初始化实例属性
        self.progress_dialog = None
        self.downloader = None
        self._preview = None

        self.central = QWidget()
        self.setCentralWidget(self.central)

        # PySide6 Enum: QFont.Bold -> QFont.Weight.Bold
        font = QFont("MiSans", 11, QFont.Weight.Bold)
        main_layout = QVBoxLayout(self.central)

        # --- 顶部操作区域 ---
        top_group = QGroupBox()
        top_group.setStyleSheet(GROUP_BOX_STYLE)
        top_layout = QHBoxLayout(top_group)

        self.btn_import = QPushButton("导入单词库 (CSV/JSON)")
        self.btn_download = QPushButton("从网络下载词库")
        self.btn_open = QPushButton("打开当前词库")
        self.btn_save = QPushButton("保存进度到文件")
        self.btn_load = QPushButton("从文件加载进度")

        for b in [self.btn_import, self.btn_download, self.btn_open, self.btn_save, self.btn_load]:
            b.setFont(font)
            b.setFixedHeight(36)
            b.setStyleSheet(BTN_STYLE)
            top_layout.addWidget(b)

        main_layout.addWidget(top_group)

        # --- 底部布局 ---
        bottom_layout = QHBoxLayout()

        # --- 左侧区域 ---
        left_group = QGroupBox()
        left_group.setStyleSheet("QGroupBox{border:1px solid #ddd;border-radius:12px;padding:12px;}")
        left_layout = QVBoxLayout(left_group)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setFixedHeight(28)
        self.progress.setStyleSheet(PROGRESS_BAR_STYLE % "#0078d7")

        self.review_progress = QProgressBar()
        self.review_progress.setFixedHeight(28)
        self.review_progress.setStyleSheet(PROGRESS_BAR_STYLE % "#ffa500")

        self.test_progress = QProgressBar()
        self.test_progress.setFixedHeight(28)
        self.test_progress.setStyleSheet(PROGRESS_BAR_STYLE % "#32cd32")

        left_layout.addWidget(QLabel("学习进度 (已学 / 全部)："))
        left_layout.addWidget(self.progress)
        left_layout.addWidget(QLabel("复习进度 (已复习 / 已学习)："))
        left_layout.addWidget(self.review_progress)
        left_layout.addWidget(QLabel("测试进度 (已测试 / 全部)："))
        left_layout.addWidget(self.test_progress)

        # 数量设置 SpinBox
        self.learn_spin = QSpinBox()
        self.learn_spin.setMaximum(999)
        self.learn_spin.setValue(self.model.settings.get("learn_count", 10))

        self.review_spin = QSpinBox()
        self.review_spin.setMaximum(999)
        self.review_spin.setValue(self.model.settings.get("review_count", 15))

        self.test_spin = QSpinBox()
        self.test_spin.setMaximum(999)
        self.test_spin.setValue(self.model.settings.get("test_count", 20))

        self.learn_spin.valueChanged.connect(lambda v: self._auto_save_setting("learn_count", v))
        self.review_spin.valueChanged.connect(lambda v: self._auto_save_setting("review_count", v))
        self.test_spin.valueChanged.connect(lambda v: self._auto_save_setting("test_count", v))

        for title, spin in [("学习模式", self.learn_spin), ("复习模式", self.review_spin),
                            ("测试模式", self.test_spin)]:
            gb = QGroupBox(title)
            gb.setStyleSheet("QGroupBox{border:1px solid #eee;border-radius:10px;padding:8px;}")
            gbl = QHBoxLayout(gb)
            gbl.addWidget(QLabel("单次单词数："))
            gbl.addWidget(spin)
            left_layout.addWidget(gb)

        bottom_layout.addWidget(left_group, 2)

        # --- 右侧区域 ---
        right_group = QGroupBox("当前单词库")
        right_group.setStyleSheet(GROUP_BOX_STYLE)
        right_layout = QVBoxLayout(right_group)

        self.wordlist_name_label = QLabel()
        name_font = QFont("MiSans", 12)
        name_font.setItalic(True)
        self.wordlist_name_label.setFont(name_font)
        self.wordlist_name_label.setStyleSheet("color: #0078d7; padding-bottom: 5px;")
        right_layout.addWidget(self.wordlist_name_label)

        self.words_view = QTextEdit()
        self.words_view.setReadOnly(True)
        right_layout.addWidget(self.words_view)
        bottom_layout.addWidget(right_group, 3)

        main_layout.addLayout(bottom_layout)

        # --- 信号连接 ---
        self.btn_import.clicked.connect(self.import_wordlist)
        self.btn_download.clicked.connect(self.download_wordlist)
        self.btn_open.clicked.connect(self.open_current_wordlist)
        self.btn_save.clicked.connect(self.save_progress_to_file)
        self.btn_load.clicked.connect(self.load_progress_from_file)

        self.refresh_view()

    def _create_backup(self):
        """
        在进行覆盖性操作前，自动备份当前进度。
        """
        backup_dir = os.path.join(self.model.data_dir, "backup")
        if not os.path.exists(backup_dir):
            try:
                os.makedirs(backup_dir)
            except OSError as e:
                print(f"创建备份目录失败: {e}")
                return

        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self.model.current_wordlist_name
        for char in '/\\:*?"<>|':
            safe_name = safe_name.replace(char, '_')

        if not safe_name:
            safe_name = "Unknown"

        filename = f"Progress_{date_str}_{safe_name}.json"
        backup_path = os.path.join(backup_dir, filename)

        try:
            self.model.save_progress(backup_path)
            print(f"已自动备份旧进度至: {backup_path}")
        except Exception as e:
            print(f"自动备份失败: {e}")

    def import_wordlist(self):
        file_filter = "单词库文件 (*.csv *.json);;CSV Files (*.csv);;JSON Files (*.json);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "选择单词库文件", "", file_filter)

        if not path:
            return

        self._create_backup()

        loaded_words = []
        if path.lower().endswith('.json'):
            loaded_words = self.model.load_words_from_json(path)
        elif path.lower().endswith('.csv'):
            loaded_words = self.model.load_words_from_csv(path)
        else:
            QMessageBox.warning(self, "导入失败", "不支持的文件类型。请选择 CSV 或 JSON 文件。")
            return

        if not loaded_words:
            QMessageBox.critical(self, "导入失败", f"文件格式错误或文件为空: {os.path.basename(path)}")
            return

        self.model.save_progress()
        QMessageBox.information(self, "导入成功",
                                f"已自动备份旧进度。\n成功导入 {len(self.model.words)} 个单词。新词库已设置为当前词库。")
        self.refresh_view()

    def download_wordlist(self):
        BASE_URL = "https://raw.githubusercontent.com/Junpgle/LearnWord/master/%E8%AF%8D%E5%BA%93/"
        available_dics = ["1-初中-顺序.json", "2-高中-顺序.json", "3-CET4-顺序.json", "4-CET6-顺序.json",
                          "5-考研-顺序.json", "6-托福-顺序.json", "7-SAT-顺序.json"]

        item, ok = QInputDialog.getItem(
            self, "下载词库", "选择要下载的词库文件:", available_dics, 0, False
        )

        if not ok or not item:
            return

        download_url = BASE_URL + item

        # PySide6 Enum: QMessageBox.StandardButton.Yes / No
        reply = QMessageBox.question(self, '确认下载',
                                     f"确认从网络下载文件: \n{item}\n这将覆盖当前词库 (旧进度将自动备份)。",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            return

        self.progress_dialog = DownloadProgressDialog(f"下载中: {item}", self)
        self.downloader = DownloadWorker(download_url, item)
        self.downloader.progress_updated.connect(self.progress_dialog.setValue)
        self.downloader.finished.connect(self.on_download_finished)
        self.progress_dialog.canceled.connect(self.downloader.stop)

        self.downloader.start()
        self.progress_dialog.exec()

    def on_download_finished(self, success, content, filename):
        self.progress_dialog.close()

        if success:
            self._import_downloaded_content(filename, content)
        else:
            if "取消" not in content and content:
                QMessageBox.critical(self, "下载失败", f"错误信息: {content}")

    def _import_downloaded_content(self, filename, content):
        """
        修复版：先保存到本地文件，再加载。
        """
        self._create_backup()

        # 1. 确保下载目录存在
        download_dir = os.path.join(self.model.data_dir, "downloads")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        # 2. 保存文件到本地 (关键步骤)
        save_path = os.path.join(download_dir, filename)
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法写入下载文件: {e}")
            return

        # 3. 从本地文件加载 (这样路径就是正确的了)
        loaded_words = []
        is_json = filename.lower().endswith('.json')
        is_csv = filename.lower().endswith('.csv')

        if is_json:
            loaded_words = self.model.load_words_from_json(save_path)
        elif is_csv:
            loaded_words = self.model.load_words_from_csv(save_path)
        else:
            QMessageBox.warning(self, "导入失败", f"不支持的文件扩展名: {filename}。")
            return

        if not loaded_words:
            QMessageBox.critical(self, "导入失败", f"下载的文件格式错误或内容为空: {filename}")
            return

        # 4. 更新设置并保存
        self.model.current_wordlist_name = f"[下载] {filename}"
        self.model.save_progress()

        QMessageBox.information(self, "导入成功",
                                f"下载并导入成功！\n文件已保存至: {save_path}\n成功导入 {len(self.model.words)} 个单词。")
        self.refresh_view()

    def open_current_wordlist(self):
        path = None
        if os.path.exists(self.model.last_json_path):
            path = self.model.last_json_path
        elif os.path.exists(self.model.last_words_path):
            path = self.model.last_words_path

        if not path:
            QMessageBox.warning(self, "打开失败", "未找到上次导入的单词库文件。")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()

            self._preview = QTextEdit()
            self._preview.setReadOnly(True)
            self._preview.setPlainText(data)
            self._preview.setWindowTitle(f"词库内容预览: {os.path.basename(path)}")
            self._preview.resize(640, 420)
            self._preview.show()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件失败: {str(e)}")

    def save_progress_to_file(self):
        self.model.settings["learn_count"] = self.learn_spin.value()
        self.model.settings["review_count"] = self.review_spin.value()
        self.model.settings["test_count"] = self.test_spin.value()
        self.model.save_settings()

        date_str = datetime.datetime.now().strftime("%Y%m%d")
        safe_name = self.model.current_wordlist_name
        for char in '/\\:*?"<>|':
            safe_name = safe_name.replace(char, '_')
        if not safe_name: safe_name = "Unknown"

        default_name = f"Progress_{date_str}_{safe_name}.json"

        default_save_path = os.path.join(self.model.data_dir, default_name)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择保存学习进度的文件",
            default_save_path,  # 使用包含 AppData 路径的完整路径
            "学习进度文件 (*.json);;所有文件 (*)"
        )

        if not path: return

        try:
            self.model.save_progress(path)
            self.model.save_progress()

            QMessageBox.information(self, "保存成功",
                                    f"设置与学习进度已保存到:\n{path}")
            self.refresh_view()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件失败: {str(e)}")

    def load_progress_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择学习进度文件",
            self.model.data_dir,  # 设置起始目录
            "学习进度文件 (*.json);;所有文件 (*)"
        )

        if not path: return

        self._create_backup()

        try:
            self.model.load_progress(path)
            self.model.save_progress()

            QMessageBox.information(self, "加载成功", f"已自动备份旧进度。\n已从 {os.path.basename(path)} 加载进度")
            self.refresh_view()
        except FileNotFoundError:
            QMessageBox.information(self, "加载失败", f"文件未找到: {path}")
        except json.JSONDecodeError:
            QMessageBox.critical(self, "加载失败", f"文件内容格式错误，无法解析为 JSON: {path}")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载文件失败: {str(e)}")

    def refresh_view(self):
        self.wordlist_name_label.setText(f"当前文件: {self.model.current_wordlist_name}")

        learned, total = self.model.get_stats()

        self.progress.setMaximum(total if total > 0 else 1)
        self.progress.setValue(learned)
        self.progress.setFormat(f"已学习 {learned} / 全部 {total}")

        learned_words = [w for w in self.model.words if w.learned]
        reviewed_words = [w for w in learned_words if w.reviewed]
        tested_words = [w for w in self.model.words if w.tested]

        learned_count = len(learned_words)
        reviewed_count = len(reviewed_words)
        tested_count = len(tested_words)

        self.review_progress.setMaximum(learned_count if learned_count > 0 else 1)
        self.review_progress.setValue(reviewed_count)
        self.review_progress.setFormat(f"已复习 {reviewed_count} / 已学习 {learned_count}")

        self.test_progress.setMaximum(total if total > 0 else 1)
        self.test_progress.setValue(tested_count)
        self.test_progress.setFormat(f"已测试 {tested_count} / 全部 {total}")

        lines = [f"[{w.stage}] {w.word} : {w.definition}" for w in self.model.words]
        self.words_view.setPlainText("\n".join(lines))

    def _auto_save_setting(self, key, value):
        self.model.settings[key] = value
        self.model.save_settings()
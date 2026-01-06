import os
import json
import requests
import datetime
import sys
# ★★★ 新增 QTabWidget, QLineEdit ★★★
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QSpinBox, QTextEdit, QGroupBox,
                               QFileDialog, QMessageBox, QInputDialog, QDialog, QFrame,
                               QTabWidget, QLineEdit, QApplication)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QMovie

from user_manager import UserManager
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
    QPushButton:disabled {
        background-color: #cccccc;
        color: #666666;
    }
"""

# 为登录框增加样式
INPUT_STYLE = """
    QLineEdit {
        border: 1px solid #ccc;
        border-radius: 6px;
        padding: 5px;
        font-size: 14px;
    }
    QLineEdit:focus {
        border: 1px solid #0078d7;
    }
"""

# --- 样式常量 ---
BTN_STYLE = """
    QPushButton {
        background-color: #0078d7;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 5px 15px;
    }
    QPushButton:hover { background-color: #339af0; }
    QPushButton:disabled { background-color: #cccccc; color: #666666; }
"""


GROUP_BOX_STYLE = "QGroupBox{border:1px solid #ddd; border-radius:12px; padding:15px; margin-top: 10px; font-weight: bold;}"

PROGRESS_BAR_STYLE = """
    QProgressBar { border: 1px solid #e0e0e0; border-radius: 10px; text-align: center; background: #f5f5f5;}
    QProgressBar::chunk { background-color: %s; border-radius: 10px; }
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
    """获取资源的绝对路径。"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.getcwd()

    full_path = os.path.join(base_path, relative_path)

    if getattr(sys, 'frozen', False) and not os.path.exists(full_path):
        base_path_exe = os.path.dirname(sys.executable)
        full_path_exe = os.path.join(base_path_exe, relative_path)
        if os.path.exists(full_path_exe):
            return full_path_exe

    return full_path


class DownloadWorker(QThread):
    """后台下载线程，支持进度条显示"""
    finished = Signal(bool, str, str)
    progress_updated = Signal(int)

    def __init__(self, url, filename):
        super().__init__()
        self.url = url
        self.filename = filename
        self._is_running = True

    def stop(self):
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
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { color: #333333; background-color: transparent; }
        """)

        layout = QVBoxLayout(self)

        self.animation_label = QLabel()
        self.animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

        layout.addWidget(self.animation_label, 1)

        self.status_label = QLabel("准备下载...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("MiSans", 10))
        layout.addWidget(self.status_label)

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


class BackupManagerDialog(QDialog):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.all_backups = self.model.get_backup_list()
        self.page_size = 5
        self.current_page = 0

        self.setWindowTitle("历史进度管理")
        self.setFixedSize(600, 500)
        self.layout = QVBoxLayout(self)

        self.list_layout = QVBoxLayout()
        self.layout.addLayout(self.list_layout)

        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("上一页")
        self.btn_next = QPushButton("下一页")
        self.page_label = QLabel()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.btn_next)
        self.layout.addLayout(nav_layout)

        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next.clicked.connect(self.next_page)
        self.refresh_page()

    def refresh_page(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        start = self.current_page * self.page_size
        end = start + self.page_size
        current_list = self.all_backups[start:end]

        for b in current_list:
            frame = QFrame()
            frame.setFrameStyle(QFrame.StyledPanel)
            f_lay = QHBoxLayout(frame)

            from datetime import datetime
            time_str = datetime.fromtimestamp(b['time']).strftime('%Y-%m-%d %H:%M')
            info = f"<b>词库:</b> {b['wordlist']}<br><b>进度:</b> {b['progress']}<br><small>{time_str}</small>"

            lbl = QLabel(info)
            lbl.setWordWrap(True)

            btn_load = QPushButton("加载")
            btn_del = QPushButton("删除")
            btn_del.setStyleSheet("background-color: #dc3545; color: white;")

            btn_load.clicked.connect(lambda chk=False, p=b['path']: self.load_backup(p))
            btn_del.clicked.connect(lambda chk=False, p=b['path']: self.delete_backup(p))

            f_lay.addWidget(lbl, 1)
            f_lay.addWidget(btn_load)
            f_lay.addWidget(btn_del)
            self.list_layout.addWidget(frame)

        self.page_label.setText(f"第 {self.current_page + 1} / {max(1, (len(self.all_backups) - 1) // 5 + 1)} 页")
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(end < len(self.all_backups))

    def load_backup(self, path):
        if QMessageBox.question(self, "确认",
                                "确定加载此进度？当前进度将被覆盖（并备份）。") == QMessageBox.StandardButton.Yes:
            self.parent()._create_backup()
            self.model.load_progress(path)
            self.model.save_progress()
            self.accept()

    def delete_backup(self, path):
        if QMessageBox.question(self, "删除", "确定永久删除此备份？") == QMessageBox.StandardButton.Yes:
            os.remove(path)
            self.all_backups = self.model.get_backup_list()
            self.refresh_page()

    def prev_page(self):
        self.current_page -= 1
        self.refresh_page()

    def next_page(self):
        self.current_page += 1
        self.refresh_page()


class SettingWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model

        # --- 增强版 UserManager 获取逻辑 (修复 AttributeError 并增强状态同步) ---
        self.user_manager = None

        # 1. 尝试从 parent (MainWindow) 及其子控件中探测
        main_win = parent
        if not main_win:
            # 如果没传 parent，从全局顶级窗口中搜寻 MainWindow
            for widget in QApplication.topLevelWidgets():
                if "MainWindow" in str(type(widget)):
                    main_win = widget
                    break

        if main_win:
            # 优先从 MainWindow 本身拿，其次从它的 account_panel 拿
            self.user_manager = getattr(main_win, 'user_manager', None)
            if not self.user_manager:
                panel = main_win.findChild(QWidget, "AccountPanel")
                self.user_manager = getattr(panel, 'user_manager', None)

        # 2. 兜底：如果实在没找着共享实例，新建一个 (UserManager 会尝试加载本地 session 文件)
        if not self.user_manager:
            self.user_manager = UserManager()

        self.setWindowTitle("设置与数据管理")

        self.setFixedSize(1000, 700)
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.main_layout = QVBoxLayout(self.central)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        self.setup_ui()
        self.refresh_view()

    def setup_ui(self):
        # 1. 顶部工具栏 (所有操作按钮并排)
        tool_group = QGroupBox("数据操作")
        tool_group.setStyleSheet(GROUP_BOX_STYLE)
        tool_layout = QHBoxLayout(tool_group)

        self.btn_import = QPushButton("导入词库")
        self.btn_download = QPushButton("下载词库")
        self.btn_manage_backup = QPushButton("历史备份")
        self.btn_cloud_backup = QPushButton("☁️ 云端备份")
        self.btn_cloud_restore = QPushButton("⬇️ 云端恢复")

        for b in [self.btn_import, self.btn_download, self.btn_manage_backup,self.btn_cloud_backup,self.btn_cloud_restore]:
            b.setStyleSheet(BTN_STYLE);
            b.setFixedHeight(38);
            tool_layout.addWidget(b)

        self.main_layout.addWidget(tool_group)

        # 2. 中间内容区
        content_layout = QHBoxLayout()
        left_side = QVBoxLayout()

        # 进度组
        progress_group = QGroupBox("进度统计");
        progress_group.setStyleSheet(GROUP_BOX_STYLE)
        prog_v = QVBoxLayout(progress_group)
        self.progress = QProgressBar();
        self.progress.setStyleSheet(PROGRESS_BAR_STYLE % "#0078d7")
        self.review_progress = QProgressBar();
        self.review_progress.setStyleSheet(PROGRESS_BAR_STYLE % "#ffa500")
        self.test_progress = QProgressBar();
        self.test_progress.setStyleSheet(PROGRESS_BAR_STYLE % "#32cd32")
        prog_v.addWidget(QLabel("学习进度："));
        prog_v.addWidget(self.progress)
        prog_v.addWidget(QLabel("复习进度："));
        prog_v.addWidget(self.review_progress)
        prog_v.addWidget(QLabel("测试进度："));
        prog_v.addWidget(self.test_progress)
        left_side.addWidget(progress_group)

        # 参数组
        set_group = QGroupBox("参数配置");
        set_group.setStyleSheet(GROUP_BOX_STYLE)
        set_v = QVBoxLayout(set_group)
        self.learn_spin = QSpinBox();
        self.review_spin = QSpinBox();
        self.test_spin = QSpinBox()
        for txt, spin, key in [("单次学习：", self.learn_spin, "learn_count"),
                               ("单次复习：", self.review_spin, "review_count"),
                               ("单次测试：", self.test_spin, "test_count")]:
            row = QHBoxLayout();
            row.addWidget(QLabel(txt));
            spin.setRange(1, 500)
            spin.setValue(self.model.settings.get(key, 20))
            spin.valueChanged.connect(lambda v, k=key: self._auto_save_setting(k, v))
            row.addWidget(spin);
            set_v.addLayout(row)
        left_side.addWidget(set_group)
        content_layout.addLayout(left_side, 2)

        # 预览组
        pre_group = QGroupBox("当前词库预览");
        pre_group.setStyleSheet(GROUP_BOX_STYLE)
        pre_v = QVBoxLayout(pre_group)
        self.wordlist_name_label = QLabel()
        self.words_view = QTextEdit();
        self.words_view.setReadOnly(True)
        pre_v.addWidget(self.wordlist_name_label);
        pre_v.addWidget(self.words_view)
        content_layout.addWidget(pre_group, 3)

        self.main_layout.addLayout(content_layout)
        self.lbl_cloud_status = QLabel();
        self.main_layout.addWidget(self.lbl_cloud_status)

        # 连信号
        self.btn_import.clicked.connect(self.import_wordlist)
        self.btn_download.clicked.connect(self.download_wordlist)
        self.btn_manage_backup.clicked.connect(self.open_backup_manager)
        self.btn_cloud_backup.clicked.connect(self.handle_backup)
        self.btn_cloud_restore.clicked.connect(self.handle_restore)

    def _create_backup(self):
        """自动备份当前进度 (修复 AttributeError)"""
        backup_dir = os.path.join(self.model.data_dir, "backup")
        if not os.path.exists(backup_dir): os.makedirs(backup_dir, exist_ok=True)
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join([c if c.isalnum() else "_" for c in self.model.current_wordlist_name])
        backup_path = os.path.join(backup_dir, f"Progress_{date_str}_{safe_name}.json")
        try:
            self.model.save_progress(backup_path)
        except Exception as e:
            print(f"Backup failed: {e}")

    def refresh_view(self):
        # --- 修改处：确保 UI 刷新时强制同步逻辑状态 ---
        is_logged = self.user_manager.is_logged_in()
        self.btn_cloud_backup.setEnabled(is_logged)
        self.btn_cloud_restore.setEnabled(is_logged)

        if is_logged:
            user = self.user_manager.get_username()
            self.lbl_cloud_status.setText(f"云端状态：已登录为 {user} (数据同步已就绪)")
            self.lbl_cloud_status.setStyleSheet("color: #28a745; font-weight: bold;")
        else:
            self.lbl_cloud_status.setText("云端状态：未登录 (请在主界面侧边栏登录账户以启用云同步)")
            self.lbl_cloud_status.setStyleSheet("color: #d32f2f;")
        # ------------------------------------------

        self.wordlist_name_label.setText(f"当前文件: {self.model.current_wordlist_name}")


    def import_wordlist(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择单词库", "", "词库文件 (*.csv *.json)")
        if path:
            self._create_backup()
            if path.lower().endswith('.json'):
                self.model.load_words_from_json(path)
            else:
                self.model.load_words_from_csv(path)
            self.model.save_progress();
            self.refresh_view()

    def download_wordlist(self):
        available = ["1-初中-顺序.json", "2-高中-顺序.json", "3-CET4-顺序.json", "4-CET6-顺序.json"]
        item, ok = QInputDialog.getItem(self, "下载词库", "选择词库:", available, 0, False)
        if ok and item:
            url = f"https://raw.githubusercontent.com/Junpgle/LearnWord/master/%E8%AF%8D%E5%BA%93/{item}"
            self.dl_dlg = DownloadProgressDialog(f"下载: {item}", self)
            self.worker = DownloadWorker(url, item)
            self.worker.progress_updated.connect(self.dl_dlg.setValue)
            self.worker.finished.connect(self._on_dl_finished);
            self.worker.start();
            self.dl_dlg.exec()

    def _on_dl_finished(self, success, content, filename):
        self.dl_dlg.close()
        if success:
            self._create_backup()
            path = os.path.join(self.model.data_dir, filename)
            with open(path, 'w', encoding='utf-8') as f: f.write(content)
            self.model.load_words_from_json(path)
            self.model.current_wordlist_name = f"[下载] {filename}"
            self.model.save_progress();
            self.refresh_view()

    def handle_backup(self):
        temp = os.path.join(self.model.data_dir, "cloud_sync_temp.json")
        self.model.save_progress(temp)
        success, msg = self.user_manager.backup_progress(temp)
        QMessageBox.information(self, "结果", "备份成功" if success else msg)
        if os.path.exists(temp): os.remove(temp)

    def handle_restore(self):
        if QMessageBox.question(self, "确认", "恢复将覆盖本地进度，是否继续？") == QMessageBox.StandardButton.Yes:
            temp = os.path.join(self.model.data_dir, "cloud_restore_temp.json")
            success, msg = self.user_manager.restore_progress(temp)
            if success:
                self._create_backup();
                self.model.load_progress(temp);
                self.model.save_progress();
                self.refresh_view()
            else:
                QMessageBox.warning(self, "失败", msg)
            if os.path.exists(temp): os.remove(temp)

    def open_backup_manager(self):
        if BackupManagerDialog(self.model, self).exec() == QDialog.DialogCode.Accepted: self.refresh_view()

    def _auto_save_setting(self, k, v):
        self.model.settings[k] = v; self.model.save_settings()

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
        self._create_backup()

        download_dir = os.path.join(self.model.data_dir, "downloads")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        save_path = os.path.join(download_dir, filename)
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法写入下载文件: {e}")
            return

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
            default_save_path,
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
            self.model.data_dir,
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

    def open_backup_manager(self):
        dlg = BackupManagerDialog(self.model, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_view()

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
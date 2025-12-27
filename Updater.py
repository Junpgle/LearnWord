import sys
import os
import json
import time
import shutil
import zipfile
import subprocess
import ctypes
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import tempfile

# ================= 关键：全局异常捕获 =================
try:
    import requests
except ImportError:
    ctypes.windll.user32.MessageBoxW(0, "缺少依赖库: requests\n请运行: pip install requests", "启动失败", 0x10)
    sys.exit(1)


# ================= 修复 Tcl/Tk 路径问题 =================
def fix_tcl_tk():
    if getattr(sys, 'frozen', False):
        return

    if sys.platform == 'win32':
        try:
            base_prefix = getattr(sys, 'base_prefix', None) or getattr(sys, 'real_prefix', None) or sys.prefix
            possible_tcl_dirs = [
                os.path.join(base_prefix, 'tcl'),
                os.path.join(base_prefix, 'Lib', 'tcl8.6'),
                os.path.join(os.path.dirname(sys.executable), 'tcl'),
                os.path.join(sys.prefix, 'tcl'),
            ]

            for tcl_root in possible_tcl_dirs:
                if os.path.exists(tcl_root):
                    found = False
                    for name in os.listdir(tcl_root):
                        if name.startswith('tcl8') and os.path.isdir(os.path.join(tcl_root, name)):
                            os.environ['TCL_LIBRARY'] = os.path.join(tcl_root, name)
                            found = True
                        if name.startswith('tk8') and os.path.isdir(os.path.join(tcl_root, name)):
                            os.environ['TK_LIBRARY'] = os.path.join(tcl_root, name)
                    if found: break
        except Exception:
            pass


fix_tcl_tk()

# ================= 配置与工具 =================
MANIFEST_URL = "https://raw.githubusercontent.com/Junpgle/LearnWord/refs/heads/master/update_manifest.json"
PATCH_BASE_URL = "https://raw.githubusercontent.com/Junpgle/LearnWord/refs/heads/master/"
MAIN_APP_EXE = "LearnWord.exe"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin(zip_path, new_ver):
    """提权逻辑"""
    executable = sys.executable
    if getattr(sys, 'frozen', False):
        params = f'--install "{zip_path}" "{new_ver}"'
    else:
        script = os.path.abspath(sys.argv[0])
        params = f'"{script}" --install "{zip_path}" "{new_ver}"'

    current_exe_dir = os.path.dirname(os.path.abspath(executable))
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, current_exe_dir, 1)
    return ret > 32


# ================= UI 与逻辑 =================
class UpdaterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LearnWord 自动更新")

        # 调整窗口大小以容纳日志列表 (高度增加到 320)
        width, height = 450, 320
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.resizable(False, False)

        # 尝试设置图标
        if os.path.exists("icon.ico"):
            try:
                root.iconbitmap("icon.ico")
            except:
                pass

        # 主容器
        main_frame = ttk.Frame(root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. 顶部标题
        self.lbl_title = ttk.Label(main_frame, text="正在准备...", font=("Microsoft YaHei", 12, "bold"))
        self.lbl_title.pack(anchor="w", pady=(0, 10))

        # 2. 日志列表区域 (使用 Text 组件模拟列表)
        self.log_text = tk.Text(
            main_frame,
            height=10,
            state="disabled",
            font=("Consolas", 9),
            bg="#f0f0f0",
            relief="flat",
            wrap="word"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 配置颜色标签
        self.log_text.tag_config("normal", foreground="#333333")
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("info", foreground="#0078d7")

        # 3. 实时状态标签 (用于显示下载的具体百分比)
        self.lbl_detail = ttk.Label(main_frame, text="", font=("Microsoft YaHei", 8), foreground="#666666")
        self.lbl_detail.pack(anchor="w", pady=(0, 2))

        # 4. 进度条
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", length=360, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(0, 5))

        self.running = True

        # 解析启动参数
        self.install_mode = False
        if "--install" in sys.argv:
            try:
                idx = sys.argv.index("--install")
                self.target_zip = sys.argv[idx + 1]
                self.target_ver = sys.argv[idx + 2]
                self.install_mode = True
            except:
                pass

        if self.install_mode:
            self.lbl_title.config(text="正在安装更新...")
            threading.Thread(target=self.run_install, daemon=True).start()
        else:
            self.lbl_title.config(text="检查更新中...")
            threading.Thread(target=self.run_check_and_download, daemon=True).start()

    # --- UI 辅助方法 ---
    def add_log(self, message, tag="normal"):
        """向日志框添加一行带项目符号的文本"""
        if not self.running: return

        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"- {message}\n", tag)
            self.log_text.see("end")  # 自动滚动到底部
            self.log_text.config(state="disabled")

        self.root.after(0, _append)

    def update_progress(self, val, detail_text=""):
        """更新进度条和详情小字"""
        if not self.running: return
        self.root.after(0, lambda: self.progress.config(value=val))
        if detail_text:
            self.root.after(0, lambda: self.lbl_detail.config(text=detail_text))

    def run_check_and_download(self):
        try:
            # 1. 检测当前版本
            local_ver = "v0.0.0"
            try:
                v_path = os.path.join(os.getenv('APPDATA'), 'LearnWord', 'data', 'version.txt')
                if os.path.exists(v_path):
                    with open(v_path, 'r', encoding='utf-8') as f: local_ver = f.read().strip()
            except:
                pass

            self.add_log(f"检测当前版本: {local_ver}")
            time.sleep(0.3)  # 稍微停顿，增加视觉上的步骤感

            # 2. 获取最新版本
            self.add_log("正在连接更新服务器...", "info")
            try:
                manifest = requests.get(f"{MANIFEST_URL}?t={int(time.time())}", timeout=10).json()
                remote_ver = manifest.get("latest_version", "v0.0.0")
                self.add_log(f"获取最新版本: {remote_ver}", "success" if remote_ver != local_ver else "normal")
            except Exception as e:
                self.add_log(f"获取版本失败: {e}", "error")
                raise

            if remote_ver == local_ver:
                self.add_log("当前已是最新版本。", "success")
                self.update_progress(100, "无需更新")
                self.root.after(1500, lambda: messagebox.information("自动更新", "当前已是最新版本。"))
                self.root.after(1500, self.root.destroy)
                return

            # 3. 增量包查询
            final_url = manifest.get("patches", {}).get(local_ver)
            is_patch = True

            if final_url:
                self.add_log("增量包查询: 已找到 (使用补丁包)", "success")
            else:
                # 尝试后备下载
                self.add_log("增量包查询: 清单中未找到，尝试全量...", "info")
                full_url = manifest.get("download_url")
                if not full_url: raise Exception("无法获取下载链接")
                final_url = full_url
                is_patch = False
                self.add_log("已切换至全量更新包下载", "normal")

            # 4. 执行下载
            self.add_log(f"正在下载{'增量' if is_patch else '全量'}更新包...", "info")

            temp_dir = tempfile.gettempdir()
            temp_zip = os.path.join(temp_dir, "learnword_update.zip")

            with requests.get(final_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                dl = 0

                with open(temp_zip, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if not self.running: return
                        f.write(chunk)
                        dl += len(chunk)

                        # 更新进度条和下方的小字详情
                        if total > 0:
                            percent = int(dl / total * 100)
                            # 格式化大小显示 (MB)
                            dl_mb = dl / 1024 / 1024
                            total_mb = total / 1024 / 1024
                            self.update_progress(percent, f"下载进度: {percent}% ({dl_mb:.1f}MB / {total_mb:.1f}MB)")

            self.add_log("下载完成，校验完整性...", "success")
            self.update_progress(100, "准备安装...")
            time.sleep(0.5)

            # 5. 触发提权
            self.add_log("正在申请安装权限...", "info")
            if is_admin():
                self.run_install(temp_zip, remote_ver)
            else:
                if run_as_admin(temp_zip, remote_ver):
                    self.root.after(0, self.root.destroy)
                else:
                    self.add_log("权限被拒绝，无法安装", "error")
                    self.root.after(0, lambda: messagebox.showwarning("权限被拒绝", "安装需要管理员权限。"))
                    self.root.after(0, self.root.destroy)

        except Exception as e:
            self.add_log(f"错误: {str(e)}", "error")
            self.root.after(0, lambda: messagebox.showerror("更新错误", str(e)))
            self.root.after(0, self.root.destroy)

    def run_install(self, zip_path=None, new_ver=None):
        try:
            zp = zip_path or self.target_zip
            nv = new_ver or self.target_ver

            if getattr(sys, 'frozen', False):
                target_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                target_dir = os.getcwd()

            self.add_log("正在关闭主程序...", "normal")
            subprocess.run(f"taskkill /F /IM {MAIN_APP_EXE}", shell=True, stderr=subprocess.DEVNULL)
            time.sleep(1.5)

            self.add_log("正在解压覆盖文件...", "info")
            with zipfile.ZipFile(zp, 'r') as zf:
                # 处理删除清单
                if "patch_manifest.json" in zf.namelist():
                    try:
                        actions = json.loads(zf.read("patch_manifest.json")).get("actions", {})
                        for d in actions.get("delete", []):
                            p = os.path.join(target_dir, d)
                            if os.path.exists(p):
                                if os.path.isdir(p):
                                    shutil.rmtree(p, ignore_errors=True)
                                else:
                                    os.remove(p)
                    except:
                        pass

                # 提取文件
                files = [f for f in zf.namelist() if f != "patch_manifest.json" and "Updater" not in f]
                count = len(files)
                for i, f in enumerate(files):
                    if not self.running: return
                    zf.extract(f, target_dir)
                    # 仅更新进度条，不频繁写日志
                    self.update_progress(int(i / count * 100), f"正在解压: {f}")

            self.add_log("文件覆盖完成", "success")

            # 更新版本号
            v_file = os.path.join(os.getenv('APPDATA'), 'LearnWord', 'data', 'version.txt')
            os.makedirs(os.path.dirname(v_file), exist_ok=True)
            with open(v_file, 'w', encoding='utf-8') as f:
                f.write(nv)
            self.add_log(f"版本号已更新至 {nv}", "success")

            self.update_progress(100, "正在重启...")
            time.sleep(1)

            main_path = os.path.join(target_dir, MAIN_APP_EXE)
            if os.path.exists(main_path):
                subprocess.Popen([main_path],
                                 creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0)

            try:
                os.remove(zp)
            except:
                pass

            self.root.after(0, self.root.destroy)
        except Exception as e:
            self.add_log(f"安装失败: {e}", "error")
            self.root.after(0, lambda: messagebox.showerror("安装失败", f"错误：\n{str(e)}"))
            self.root.after(0, self.root.destroy)


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = UpdaterApp(root)
        root.mainloop()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"程序初始化失败:\n{str(e)}", "系统错误", 0x10)
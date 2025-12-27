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
    # 打包后的 EXE 不需要手动修复，PyInstaller 会自动处理
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
    """
    提权逻辑：针对 Program Files 目录进行优化
    """
    # 打包后的 sys.executable 就是 EXE 路径
    executable = sys.executable
    if getattr(sys, 'frozen', False):
        params = f'--install "{zip_path}" "{new_ver}"'
    else:
        script = os.path.abspath(sys.argv[0])
        params = f'"{script}" --install "{zip_path}" "{new_ver}"'

    # 获取 EXE 所在的真实目录，作为提权后的起始路径
    current_exe_dir = os.path.dirname(os.path.abspath(executable))

    # 使用 runas 触发 UAC
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, current_exe_dir, 1)
    return ret > 32


# ================= UI 与逻辑 =================
class UpdaterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LearnWord 自动更新")

        # 窗口布局
        width, height = 400, 180
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.resizable(False, False)

        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.lbl_title = ttk.Label(main_frame, text="正在准备...", font=("Microsoft YaHei", 12, "bold"))
        self.lbl_title.pack(pady=(0, 15))

        self.lbl_status = ttk.Label(main_frame, text="检查更新...", font=("Microsoft YaHei", 9))
        self.lbl_status.pack(anchor="w", pady=(0, 5))

        self.progress = ttk.Progressbar(main_frame, orient="horizontal", length=360, mode="determinate")
        self.progress.pack(pady=(0, 15), fill=tk.X)

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
            self.lbl_title.config(text="正在应用更新...")
            threading.Thread(target=self.run_install, daemon=True).start()
        else:
            self.lbl_title.config(text="正在检查新版本...")
            threading.Thread(target=self.run_check_and_download, daemon=True).start()

    def update_ui(self, title=None, status=None, progress=None):
        if not self.running: return
        if title: self.root.after(0, lambda: self.lbl_title.config(text=title))
        if status: self.root.after(0, lambda: self.lbl_status.config(text=status))
        if progress is not None: self.root.after(0, lambda: self.progress.config(value=progress))

    def run_check_and_download(self):
        try:
            # 1. 读取本地版本
            local_ver = "v0.0.0"
            try:
                v_path = os.path.join(os.getenv('APPDATA'), 'LearnWord', 'data', 'version.txt')
                if os.path.exists(v_path):
                    with open(v_path, 'r', encoding='utf-8') as f: local_ver = f.read().strip()
            except:
                pass

            self.update_ui(status=f"当前版本: {local_ver}")

            # 2. 获取清单
            manifest = requests.get(f"{MANIFEST_URL}?t={int(time.time())}", timeout=10).json()
            remote_ver = manifest.get("latest_version", "v0.0.0")

            if remote_ver == local_ver:
                self.root.after(0, lambda: messagebox.information("自动更新", f"当前已是最新版本 ({local_ver})。"))
                self.root.after(0, self.root.destroy)
                return

            self.update_ui(title="发现新版本", status=f"准备下载 {remote_ver}...")

            # 3. 匹配下载地址
            final_url = manifest.get("patches", {}).get(local_ver)
            if not final_url:
                final_url = manifest.get("download_url")

            if not final_url: raise Exception("无法获取下载链接")

            # 4. 执行下载 - 关键：下载到用户可写的临时目录
            temp_dir = tempfile.gettempdir()
            temp_zip = os.path.join(temp_dir, "learnword_update.zip")

            self.update_ui(status="开始下载更新包...")
            with requests.get(final_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                dl = 0
                with open(temp_zip, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if not self.running: return
                        f.write(chunk)
                        dl += len(chunk)
                        if total > 0: self.update_ui(progress=int(dl / total * 100),
                                                     status=f"下载进度: {int(dl / total * 100)}%")

            # 5. 触发提权
            self.update_ui(status="下载完成，正在申请安装权限...")
            time.sleep(0.5)

            if is_admin():
                self.run_install(temp_zip, remote_ver)
            else:
                if run_as_admin(temp_zip, remote_ver):
                    self.root.after(0, self.root.destroy)
                else:
                    self.root.after(0, lambda: messagebox.showwarning("权限被拒绝", "安装需要管理员权限。"))
                    self.root.after(0, self.root.destroy)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("更新错误", str(e)))
            self.root.after(0, self.root.destroy)

    def run_install(self, zip_path=None, new_ver=None):
        try:
            zp = zip_path or self.target_zip
            nv = new_ver or self.target_ver

            # 定位主程序目录 (EXE所在的文件夹)
            if getattr(sys, 'frozen', False):
                target_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                target_dir = os.getcwd()

            self.update_ui(status="正在清理主程序进程...")
            subprocess.run(f"taskkill /F /IM {MAIN_APP_EXE}", shell=True, stderr=subprocess.DEVNULL)
            time.sleep(1.5)

            self.update_ui(status="正在应用更新...")
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
                for i, f in enumerate(files):
                    if not self.running: return
                    zf.extract(f, target_dir)
                    if i % 10 == 0: self.update_ui(progress=int(i / len(files) * 100), status=f"解压中: {f}")

            # 更新版本号
            v_file = os.path.join(os.getenv('APPDATA'), 'LearnWord', 'data', 'version.txt')
            os.makedirs(os.path.dirname(v_file), exist_ok=True)
            with open(v_file, 'w', encoding='utf-8') as f:
                f.write(nv)

            self.update_ui(status="更新成功！正在重启主程序...", progress=100)
            time.sleep(1)

            main_path = os.path.join(target_dir, MAIN_APP_EXE)
            if os.path.exists(main_path):
                # 以非继承模式启动主程序
                subprocess.Popen([main_path],
                                 creationflags=subprocess.DETACHED_PROCESS if sys.platform == 'win32' else 0)

            # 尝试删除临时下载包
            try:
                os.remove(zp)
            except:
                pass

            self.root.after(0, self.root.destroy)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("安装失败", f"权限错误或文件占用：\n{str(e)}"))
            self.root.after(0, self.root.destroy)


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = UpdaterApp(root)
        root.mainloop()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"程序初始化失败:\n{str(e)}", "系统错误", 0x10)
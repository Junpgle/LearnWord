# --- 终极兼容性补丁保持不变 ---
import sys
from types import ModuleType


class DummySecureCookie:
    @classmethod
    def load_cookie(cls, *args, **kwargs): return {}

    def __init__(self, *args, **kwargs): pass


try:
    import werkzeug

    try:
        from werkzeug.local import LocalProxy

        werkzeug.LocalProxy = LocalProxy
    except ImportError:
        pass
    contrib = ModuleType('werkzeug.contrib')
    sys.modules['werkzeug.contrib'] = contrib
    sc_module = ModuleType('werkzeug.contrib.securecookie')
    sys.modules['werkzeug.contrib.securecookie'] = sc_module
    try:
        import secure_cookie

        if hasattr(secure_cookie, 'SecureCookie'):
            sc_module.SecureCookie = secure_cookie.SecureCookie
        else:
            sc_module.SecureCookie = DummySecureCookie
    except ImportError:
        sc_module.SecureCookie = DummySecureCookie
except Exception as e:
    print(f"Patch apply warning: {e}")

import leancloud
import os
import shutil


class UserManager:
    def __init__(self):
        self.APP_ID = "5wPsbnakcoOjfaPzfC44vfW5-gzGzoHsz"
        self.APP_KEY = "j9qbdfjiJAPsqbGUy04COFTD"
        # 初始化 LeanCloud
        leancloud.init(self.APP_ID, self.APP_KEY)
        self.current_user = leancloud.User.get_current()

    def is_logged_in(self):
        return self.current_user is not None

    def get_username(self):
        if self.current_user:
            return self.current_user.get_username()
        return None

    def login(self, username, password):
        try:
            self.current_user = leancloud.User()
            self.current_user.login(username, password)
            return True, "登录成功"
        except leancloud.LeanCloudError as e:
            return False, f"登录失败: {e}"

    def register(self, username, password, email=None):
        try:
            user = leancloud.User()
            user.set_username(username)
            user.set_password(password)
            if email: user.set_email(email)
            user.sign_up()
            self.current_user = user
            return True, "注册成功"
        except leancloud.LeanCloudError as e:
            return False, f"注册失败: {e}"

    def logout(self):
        if self.current_user:
            self.current_user.logout()
            self.current_user = None

    def backup_progress(self, file_path, stats_dict=None):
        """
        上传进度文件到云端，并同步统计数据
        :param file_path: 本地进度 JSON 路径
        :param stats_dict: 包含统计信息的字典，例如:
               {"wordlist_name": "CET4", "learned_count": 100, "total_count": 4000, "reviewed_count": 50, "tested_count": 20}
        """
        if not self.is_logged_in(): return False, "请先登录"
        if not os.path.exists(file_path): return False, "找不到本地进度文件"

        try:
            with open(file_path, 'rb') as f:
                lc_file = leancloud.File(f'progress_{self.get_username()}.json', f)
                lc_file.save()

            self.current_user.set('backupFileUrl', lc_file.url)

            # --- 新增：将统计信息同步到 User 表字段 ---
            if stats_dict:
                self.current_user.set('wordlistName', stats_dict.get('wordlist_name', '未记录'))
                self.current_user.set('learnedCount', stats_dict.get('learned_count', 0))
                self.current_user.set('totalCount', stats_dict.get('total_count', 0))
                self.current_user.set('reviewedCount', stats_dict.get('reviewed_count', 0))
                self.current_user.set('testedCount', stats_dict.get('tested_count', 0))

            self.current_user.save()
            return True, "备份成功！"
        except Exception as e:
            return False, f"备份失败: {str(e)}"

    def restore_progress(self, save_path):
        if not self.is_logged_in(): return False, "请先登录"
        try:
            self.current_user.fetch()
            backup_url = self.current_user.get('backupFileUrl')
            if not backup_url: return False, "云端没有找到备份记录"

            import requests
            response = requests.get(backup_url)
            if response.status_code == 200:
                if os.path.exists(save_path): shutil.copy(save_path, save_path + ".bak")
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                return True, "恢复成功！请重启软件以生效。"
            return False, "下载文件失败"
        except Exception as e:
            return False, f"恢复失败: {str(e)}"
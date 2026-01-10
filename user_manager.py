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
import json
import time


class UserManager:
    def __init__(self):
        self.APP_ID = "5wPsbnakcoOjfaPzfC44vfW5-gzGzoHsz"
        self.APP_KEY = "j9qbdfjiJAPsqbGUy04COFTD"
        # 初始化 LeanCloud
        leancloud.init(self.APP_ID, self.APP_KEY)

        # 会话配置
        self.SESSION_FILE = os.path.join(os.path.expanduser("~"), ".learnword_session.json")
        self.SESSION_EXPIRE_DAYS = 7

        # 尝试恢复之前保存的会话
        self.current_user = self._restore_session() or leancloud.User.get_current()

    def is_logged_in(self):
        return self.current_user is not None

    def get_username(self):
        if self.current_user:
            return self.current_user.get_username()
        return None

    def _save_session(self):
        """保存会话信息到本地文件"""
        if not self.current_user:
            return
        try:
            session_data = {
                "username": self.current_user.get_username(),
                "session_token": self.current_user.get_session_token(),
                "saved_at": time.time()
            }
            with open(self.SESSION_FILE, 'w') as f:
                json.dump(session_data, f)
        except Exception as e:
            print(f"保存会话失败: {e}")

    def _restore_session(self):
        """尝试从本地文件恢复会话"""
        if not os.path.exists(self.SESSION_FILE):
            return None

        try:
            with open(self.SESSION_FILE, 'r') as f:
                session_data = json.load(f)

            # 检查会话是否过期
            saved_at = session_data.get('saved_at', 0)
            elapsed_days = (time.time() - saved_at) / (24 * 3600)

            if elapsed_days > self.SESSION_EXPIRE_DAYS:
                # 会话已过期，删除文件
                os.remove(self.SESSION_FILE)
                return None

            # 尝试使用保存的 session token 恢复用户对象
            session_token = session_data.get('session_token')
            username = session_data.get('username')

            if session_token and username:
                user = leancloud.User()
                user.set_username(username)
                user._session_token = session_token

                # 验证 token 是否仍然有效
                try:
                    user.fetch()
                    return user
                except:
                    # Token 失效，删除文件
                    os.remove(self.SESSION_FILE)
                    return None
        except Exception as e:
            print(f"恢复会话失败: {e}")
            return None

    def _clear_session(self):
        """清除本地保存的会话"""
        if os.path.exists(self.SESSION_FILE):
            try:
                os.remove(self.SESSION_FILE)
            except Exception as e:
                print(f"清除会话失败: {e}")

    def login(self, username, password):
        try:
            self.current_user = leancloud.User()
            self.current_user.login(username, password)
            self._save_session()  # 登录成功后保存会话
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
        self._clear_session()  # 登出时清除保存的会话

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
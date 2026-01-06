# --- 终极兼容性补丁：彻底解决 LeanCloud + Werkzeug + Python 3.13 的导入死锁 ---
import sys
from types import ModuleType


# 1. 预先定义一个假的 SecureCookie 类，防止 SDK 崩溃
class DummySecureCookie:
    @classmethod
    def load_cookie(cls, *args, **kwargs): return {}

    def __init__(self, *args, **kwargs): pass


# 2. 伪造整个 werkzeug.contrib.securecookie 模块路径
try:
    import werkzeug

    # 修复 LocalProxy
    try:
        from werkzeug.local import LocalProxy

        werkzeug.LocalProxy = LocalProxy
    except ImportError:
        pass

    # 创建虚假的 contrib 模块层级
    contrib = ModuleType('werkzeug.contrib')
    sys.modules['werkzeug.contrib'] = contrib

    # 创建虚假的 securecookie 模块
    sc_module = ModuleType('werkzeug.contrib.securecookie')
    sys.modules['werkzeug.contrib.securecookie'] = sc_module

    # 尝试从安装的库里找，找不到就用我们定义的 Dummy 类
    try:
        import secure_cookie

        if hasattr(secure_cookie, 'SecureCookie'):
            sc_module.SecureCookie = secure_cookie.SecureCookie
        elif hasattr(secure_cookie, 'securecookie'):
            sc_module.SecureCookie = secure_cookie.securecookie
        else:
            sc_module.SecureCookie = DummySecureCookie
    except ImportError:
        sc_module.SecureCookie = DummySecureCookie

except Exception as e:
    print(f"Patch apply warning: {e}")

# 3. 针对 Python 3.13 的 gevent 补丁 (防止底层阻塞)
# 如果后续运行报错 'gevent' 相关，取消下面两行的注释
# import os
# os.environ['GEVENT_CORE_CFFI_ONLY'] = '1'
# -----------------------------------------------------------------------


import leancloud
import os
import shutil


class UserManager:
    def __init__(self):
        # ★★★ 请在这里填入你的 LeanCloud AppID 和 AppKey ★★★
        # 建议：如果发布给别人用，不要把 MasterKey 写在这里
        self.APP_ID = "5wPsbnakcoOjfaPzfC44vfW5-gzGzoHsz"
        self.APP_KEY = "j9qbdfjiJAPsqbGUy04COFTD"
        server_url = "https://5wpsbnak.lc-cn-n1-shared.com"

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
            if email:
                user.set_email(email)
            user.sign_up()
            self.current_user = user
            return True, "注册成功"
        except leancloud.LeanCloudError as e:
            return False, f"注册失败: {e}"

    def logout(self):
        if self.current_user:
            self.current_user.logout()
            self.current_user = None

    def backup_progress(self, file_path):
        """上传进度文件到云端"""
        if not self.is_logged_in():
            return False, "请先登录"

        if not os.path.exists(file_path):
            return False, "找不到本地进度文件"

        try:
            with open(file_path, 'rb') as f:
                # 创建 LeanCloud 文件对象
                lc_file = leancloud.File(f'progress_{self.get_username()}.json', f)
                lc_file.save()

            # 将文件关联到当前用户（覆盖旧的关联或保存为新字段）
            # 这里我们简单地保存文件的 URL 到用户的一个字段 'backupFileUrl'
            self.current_user.set('backupFileUrl', lc_file.url)
            self.current_user.save()
            return True, "备份成功！"
        except Exception as e:
            return False, f"备份失败: {str(e)}"

    def restore_progress(self, save_path):
        """从云端下载进度文件并覆盖本地"""
        if not self.is_logged_in():
            return False, "请先登录"

        try:
            # 获取用户最后一次备份的文件 URL
            # 注意：需要重新 fetch 一下用户数据以确保拿到最新字段
            self.current_user.fetch()
            backup_url = self.current_user.get('backupFileUrl')

            if not backup_url:
                return False, "云端没有找到备份记录"

            # 下载文件
            import requests
            response = requests.get(backup_url)
            if response.status_code == 200:
                # 备份当前的本地文件以防万一
                if os.path.exists(save_path):
                    shutil.copy(save_path, save_path + ".bak")

                # 写入新文件
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                return True, "恢复成功！请重启软件以生效。"
            else:
                return False, "下载文件失败"
        except Exception as e:
            return False, f"恢复失败: {str(e)}"
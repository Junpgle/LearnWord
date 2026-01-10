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
        # 使用应用数据目录存储会话文件
        app_data_dir = os.path.join(os.getenv('APPDATA'), 'LearnWord')
        os.makedirs(app_data_dir, exist_ok=True)
        self.SESSION_FILE = os.path.join(app_data_dir, 'session.json')
        self.REMEMBER_FILE = os.path.join(app_data_dir, 'remember.json')
        self.SESSION_EXPIRE_DAYS = 7

        print("\n" + "="*60)
        print("[UserManager] 初始化")
        print(f"[UserManager] APP_ID: {self.APP_ID[:20]}...")
        print(f"[UserManager] 会话文件: {self.SESSION_FILE}")
        print(f"[UserManager] 记住密码文件: {self.REMEMBER_FILE}")
        print("="*60)

        # 尝试恢复之前保存的会话
        restored_user = self._restore_session()
        if restored_user:
            self.current_user = restored_user
            print(f"[UserManager] ✅ 初始化完成，自动恢复用户: {self.current_user.get_username()}")
        else:
            self.current_user = leancloud.User.get_current()
            if self.current_user:
                print(f"[UserManager] ℹ️  从 LeanCloud 获取当前用户: {self.current_user.get_username()}")
            else:
                print("[UserManager] 未登录或会话过期")
        print("="*60 + "\n")

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
            # 尝试多种方式获取 session token
            session_token = None

            # 方法1: 尝试 get() 方法
            try:
                session_token = self.current_user.get('sessionToken')
                print(f"[Token 获取] 方法1 成功: {session_token[:10]}...")
            except Exception as e1:
                print(f"[Token 获取] 方法1 失败: {e1}")

            # 方法2: 尝试私有属性
            if not session_token:
                try:
                    session_token = self.current_user._session_token
                    print(f"[Token 获取] 方法2 成功: {session_token[:10]}...")
                except Exception as e2:
                    print(f"[Token 获取] 方法2 失败: {e2}")

            # 方法3: 尝试直接属性访问
            if not session_token:
                try:
                    session_token = getattr(self.current_user, 'sessionToken', None)
                    if session_token:
                        print(f"[Token 获取] 方法3 成功: {session_token[:10]}...")
                except Exception as e3:
                    print(f"[Token 获取] 方法3 失败: {e3}")

            # 方法4: 遍历所有属性寻找 token
            if not session_token:
                print("[Token 获取] 尝试遍历对象属性...")
                for attr in dir(self.current_user):
                    if 'token' in attr.lower() or 'session' in attr.lower():
                        try:
                            val = getattr(self.current_user, attr)
                            if isinstance(val, str) and len(val) > 20:
                                session_token = val
                                print(f"[Token 获取] 方法4 成功，属性: {attr}, Token: {val[:10]}...")
                                break
                        except:
                            pass

            if not session_token:
                print("警告：无法获取 session token，可能导致会话恢复失败")
                return

            username = self.current_user.get_username()
            print(f"保存会话: 用户={username}, Token长度={len(session_token)}")

            session_data = {
                "username": username,
                "session_token": session_token,
                "saved_at": time.time()
            }
            with open(self.SESSION_FILE, 'w') as f:
                json.dump(session_data, f)
            print(f"✅ 会话已保存到: {self.SESSION_FILE}")
        except Exception as e:
            print(f"❌ 保存会话失败: {e}")
            import traceback
            traceback.print_exc()

    def _restore_session(self):
        """尝试从本地文件恢复会话"""
        if not os.path.exists(self.SESSION_FILE):
            print(f"[会话恢复] 会话文件不存在: {self.SESSION_FILE}")
            return None

        try:
            with open(self.SESSION_FILE, 'r') as f:
                session_data = json.load(f)
            print(f"[会话恢复] ✅ 读取会话文件成功: 用户={session_data.get('username')}")

            # 检查会话是否过期
            saved_at = session_data.get('saved_at', 0)
            elapsed_days = (time.time() - saved_at) / (24 * 3600)
            print(f"[会话恢复] 会话已保存 {elapsed_days:.1f} 天")

            if elapsed_days > self.SESSION_EXPIRE_DAYS:
                print(f"[会话恢复] ⏰ 会话已过期（超过 {self.SESSION_EXPIRE_DAYS} 天），删除文件")
                os.remove(self.SESSION_FILE)
                return None

            session_token = session_data.get('session_token')
            username = session_data.get('username')

            print(f"[会话恢复] 尝试恢复会话: username={username}, token_len={len(session_token or '')}")

            if not session_token or not username:
                print("[会话恢复] ❌ 会话数据不完整")
                return None

            # 方式1: 使用 become() 恢复（推荐）
            try:
                print(f"[会话恢复] 尝试 become() 方法...")
                user = leancloud.User.become(session_token)
                fetched_username = user.get_username()
                print(f"[会话恢复] ✅ become() 恢复成功: {fetched_username}")
                return user
            except Exception as e1:
                print(f"[会话恢复] become() 失败: {type(e1).__name__}: {e1}")

            # 方式2: 手动构造 User 对象
            try:
                print(f"[会话恢复] 尝试手动恢复方法...")
                user = leancloud.User()
                user._username = username
                user._session_token = session_token
                print(f"[会话恢复] 验证 token 有效性...")
                user.fetch()
                print(f"[会话恢复] ✅ 手动恢复成功: {user.get_username()}")
                return user
            except Exception as e2:
                print(f"[会话恢复] 手动恢复失败: {type(e2).__name__}: {e2}")
                print(f"[会话恢复] 删除过期会话文件...")
                try:
                    os.remove(self.SESSION_FILE)
                except:
                    pass
                return None

        except json.JSONDecodeError as e:
            print(f"[会话恢复] ❌ 会话文件格式错误: {e}")
            return None
        except Exception as e:
            print(f"[会话恢复] ❌ 异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _clear_session(self):
        """清除本地保存的会话"""
        if os.path.exists(self.SESSION_FILE):
            try:
                os.remove(self.SESSION_FILE)
            except Exception as e:
                print(f"清除会话失败: {e}")

    def save_remember_password(self, username, password):
        """保存用户名和密码（用于记住密码功能）"""
        try:
            # 简单的 Base64 编码（不是加密，只是混淆，防止明文存储）
            import base64
            encoded_pwd = base64.b64encode(password.encode()).decode()

            remember_data = {
                "username": username,
                "password": encoded_pwd,
                "saved_at": time.time()
            }
            with open(self.REMEMBER_FILE, 'w') as f:
                json.dump(remember_data, f)
            print(f"[记住密码] ✅ 已保存用户: {username}")
        except Exception as e:
            print(f"[记住密码] ❌ 保存失败: {e}")

    def get_remember_password(self):
        """读取保存的用户名和密码"""
        if not os.path.exists(self.REMEMBER_FILE):
            print(f"[记住密码] 未保存凭据")
            return None, None

        try:
            with open(self.REMEMBER_FILE, 'r') as f:
                remember_data = json.load(f)

            # Base64 解码
            import base64
            username = remember_data.get('username')
            encoded_pwd = remember_data.get('password')
            password = base64.b64decode(encoded_pwd).decode() if encoded_pwd else None

            print(f"[记住密码] ✅ 读取到保存的凭据: {username}")
            return username, password
        except Exception as e:
            print(f"[记住密码] ❌ 读取失败: {e}")
            return None, None

    def clear_remember_password(self):
        """清除保存的凭据"""
        if os.path.exists(self.REMEMBER_FILE):
            try:
                os.remove(self.REMEMBER_FILE)
                print(f"[记住密码] ✅ 已清除保存的凭据")
            except Exception as e:
                print(f"[记住密码] ❌ 清除失败: {e}")

    def login(self, username, password):
        try:
            self.current_user = leancloud.User()
            self.current_user.login(username, password)
            print(f"登录成功: {username}")
            print(f"Session Token: {self.current_user.get('sessionToken')}")
            self._save_session()  # 登录成功后保存会话
            return True, "登录成功"
        except leancloud.LeanCloudError as e:
            print(f"登录失败: {e}")
            return False, f"登录失败: {e}"

    def register(self, username, password, email=None):
        try:
            user = leancloud.User()
            user.set_username(username)
            user.set_password(password)
            if email: user.set_email(email)
            user.sign_up()
            self.current_user = user
            self._save_session()  # 注册后也保存会话
            return True, "注册成功"
        except leancloud.LeanCloudError as e:
            return False, f"注册失败: {e}"

    def logout(self):
        if self.current_user:
            self.current_user.logout()
            self.current_user = None
        self._clear_session()  # 登出时清除保存的会话
        self.clear_remember_password()  # 登出时清除记住的密码

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

    def debug_session(self):
        """调试会话信息"""
        print("="*50)
        print("会话调试信息")
        print("="*50)
        print(f"会话文件: {self.SESSION_FILE}")
        print(f"文件存在: {os.path.exists(self.SESSION_FILE)}")

        if os.path.exists(self.SESSION_FILE):
            try:
                with open(self.SESSION_FILE, 'r') as f:
                    data = json.load(f)
                    print(f"保存的用户名: {data.get('username')}")
                    print(f"Token 长度: {len(data.get('session_token', ''))}")
                    print(f"保存时间: {time.ctime(data.get('saved_at', 0))}")
            except Exception as e:
                print(f"读取文件失败: {e}")

        print(f"当前登录用户: {self.get_username()}")
        print(f"是否登录: {self.is_logged_in()}")
        print("="*50)

# 📘 LearnWord — 沉浸式桌面端单词记忆工具

> **让记忆从被动接收，走向主动输出**  
> 🌐 [**官方介绍网页**](https://junpgle.github.io/LearnWord/) | 💾 [GitHub Releases](https://github.com/Junpgle/LearnWord/releases)

LearnWord 是一款专为高效英语词汇记忆打造的现代化桌面应用。它摒弃传统“翻卡片”式的浅层学习，通过**算法驱动的三阶段记忆闭环（认知 → 自测 → 输出）**，强制大脑进行深度加工，实现真正牢固的记忆。

基于 **PySide6** 构建，拥有极简深色 UI，并针对 **Windows 系统** 进行深度优化（如 AppData 数据隔离、高 DPI 适配），确保流畅、稳定、无权限困扰的使用体验。

---

## ✨ 核心特性

### 🧠 科学记忆体系

#### 🔁 三阶段递进学习法
| 阶段 | 模式 | 目标 | 成功 | 失败 |
|------|------|------|------|------|
| **Stage 1** | **词义选择** | 建立单词与释义的初步联系 | ➡️ 晋升 Stage 2 | ❌ 停留本阶段，显示正确答案 |
| **Stage 2** | **记忆自测** | 主动回想释义（遮盖提示） | ➡️ 晋升 Stage 3 | ⬅️ 降级回 Stage 1（强化惩罚） |
| **Stage 3** | **拼写填空** | 根据语境与提示拼出完整单词 | ✅ 标记为“已掌握” | ⬅️ 降级回 Stage 1 |

#### 📉 艾宾浩斯智能复习
- 自动将已学单词按遗忘曲线加入复习队列
- 动态调整复习频率，对抗记忆衰退

#### 📝 高压测试模式（Exam Mode）
- 模拟真实考场环境
- 实时计算**拼写准确率**与**得分**
- 强化应试能力与心理抗压

---

### 🛠️ 强大功能模块

- **☁️ 云端词库中心**  
  一键从 GitHub 下载主流词库：CET-4/6、考研、托福、GRE 等。
  
- **📥 多格式本地导入**  
  - `.csv`：需包含 `单词, 词性, 释义`（支持无表头）
  - `.json`：格式为 `[{"word": "apple", "trans": "n. 苹果"}, ...]`

- **📊 可视化进度仪表盘**  
  首页实时展示 **学习 / 复习 / 测试** 三大维度进度条

- **🔄 智能热更新机制**  
  - 启动时自动检测远程 `update_manifest.json`
  - **增量修复**：仅更新变动资源（如修正词库）
  - **全量更新**：代码逻辑变更时提示下载新版 EXE

---

### 💻 极致技术体验

- **🔐 无感数据同步**  
  用户数据存储于 `%APPDATA%\LearnWord\data`，天然支持多用户隔离，无需管理员权限。

- **📦 零依赖运行**  
  通过 PyInstaller 打包为独立 `.exe`，无需安装 Python 或其他运行环境。

- **🖥️ 高清适配**  
  内置 **MiSans 字体**，完美支持高 DPI 缩放，告别模糊界面。

---

## 🚀 快速开始

想先了解再下载？👉 访问我们的 **[官方介绍网页](https://junpgle.github.io/LearnWord/)** 查看功能演示与界面预览！

### 👤 普通用户
1. 访问 [Releases 页面](https://github.com/Junpgle/LearnWord/releases) 下载 `LearnWord.zip`
2. 解压后直接运行 `LearnWord.exe`（建议创建桌面快捷方式）
3. 首次启动将自动初始化配置，数据目录：  
   `C:\Users\<用户名>\AppData\Roaming\LearnWord\data`

### 👨‍💻 开发者

#### 1. 环境准备
```bash
git clone https://github.com/Junpgle/LearnWord.git
cd LearnWord

python -m venv venv
.\venv\Scripts\activate

pip install PySide6 requests
```

#### 2. 运行源码
```bash
python main.py
```

#### 3. 打包发布（PowerShell）
```powershell
pyinstaller --noconfirm --onedir --windowed `
 --name "LearnWord" `
 --add-data "MiSans.ttf;." `
 --add-data "icon.ico;." `
 --add-data "Animation;Animation" `
 --icon "icon.ico" `
 "main.py"
```

---

## 📖 使用指南

### 学习流程说明
- 单词按掌握程度在 **Stage 1 → 2 → 3** 流转
- 仅当成功完成 **Stage 3 拼写**，才视为“已掌握”
- 所有进度持久化保存于 `progress.json`

### 词库管理（Settings）
点击主界面右下角 **Settings** 磁贴：
- **云端下载**：自动解压 Gzip 并切换词库
- **本地导入**：支持 CSV / JSON，即时生效

---

## 📂 项目结构与数据存储

为规避 Windows `Program Files` 权限限制，采用 **动静分离架构**：

### 🔒 静态资源（只读）
- 打包于 EXE 内部（`sys._MEIPASS`）或 `_internal/` 目录
  - `MiSans.ttf`（字体）
  - `icon.ico`（应用图标）
  - `Animation/`（加载动画）

### 📝 用户数据（读写）
路径：`%APPDATA%\LearnWord\data`
- `progress.json`：记录每个单词的 stage、复习次数、测试得分
- `settings.json`：当前词库路径、每日学习目标等
- `downloads/`：缓存下载的词库文件
- `announcement_state.json`：公告阅读状态


---

## 🤝 贡献指南

欢迎社区参与！
1. Fork 本仓库
2. 在 `dev` 分支开发（如新增词库解析、UI 优化）
3. 提交 Pull Request

---

## 📄 许可证

本项目基于 **MIT License** 开源。

> Copyright © 2025 Junpgle  
> 允许自由使用、修改与分发，但须保留原作者版权声明。

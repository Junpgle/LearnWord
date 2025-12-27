@echo off
:: 设置 CMD 窗口编码为 UTF-8，防止显示乱码
chcp 65001 >nul
title LearnWord 构建工具启动器

echo ==========================================
echo      正在准备构建环境...
echo ==========================================
echo.

:: 核心修改：使用 -Command 配合 Get-Content -Encoding UTF8
:: 这会强制 PowerShell 以 UTF-8 格式读取脚本内容并执行，彻底解决中文乱码导致的语法错误
PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& { $content = Get-Content -LiteralPath '%~dp0build_all.ps1' -Raw -Encoding UTF8; Invoke-Expression $content }"

:: 脚本运行完毕后暂停
echo.
echo ==========================================
echo   脚本执行结束。
echo ==========================================
pause
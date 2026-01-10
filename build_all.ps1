# Set error preference: Stop immediately on error
$ErrorActionPreference = "Stop"

try {
    # Try to adjust console buffer size
    if ($Host.Name -eq 'ConsoleHost') {
        try { $Host.UI.RawUI.BufferSize = New-Object Management.Automation.Host.Size(120, 3000) } catch {}
    }

    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "      LearnWord Build Tool (v2.1 Fix)     " -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""

    # 0. Environment Check
    if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
        throw "Error: 'pyinstaller' not found!`nPlease run: pip install pyinstaller"
    }

    # 检查 leancloud 是否安装，防止无效打包
    try {
        python -c "import leancloud" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Warning: 'leancloud' module might be missing in this environment." -ForegroundColor Red
            Write-Host "Attempting to install..." -ForegroundColor Yellow
            pip install leancloud
        }
    } catch {}

    # 1. Build Main Program (LearnWord)
    Write-Host "[1/3] Building Main Program (LearnWord)..." -ForegroundColor Yellow

    # 【修复】添加 --hidden-import leancloud 强制打包云端数据库库
    $buildCmd1 = "pyinstaller --noconfirm --onedir --windowed --clean --name `"LearnWord`" --icon `"icon.ico`" --hidden-import leancloud --add-data `"MiSans.ttf;.`" --add-data `"Animation;Animation`" main.py"

    cmd /c $buildCmd1
    if ($LASTEXITCODE -ne 0) { throw "Main program build failed!" }

    # 2. Build Updater (Tkinter based - Ultra Slim)
    Write-Host "`n[2/3] Building Updater (Tkinter Slim Mode)..." -ForegroundColor Yellow

    # 强制排除所有 PySide6 和 Qt 相关库
    $excludes = "--exclude-module PySide6 --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module matplotlib --exclude-module numpy --exclude-module pandas --exclude-module PIL"

    $buildCmd2 = "pyinstaller --noconfirm --onefile --windowed --clean --name `"Updater`" --icon `"icon.ico`" $excludes updater.py"
    cmd /c $buildCmd2
    if ($LASTEXITCODE -ne 0) { throw "Updater build failed!" }

    # 3. Integrate Files
    Write-Host "`n[3/3] Moving files..." -ForegroundColor Yellow

    $MainDir = Join-Path "dist" "LearnWord"
    $UpdaterExe = Join-Path "dist" "Updater.exe"

    if (Test-Path $UpdaterExe) {
        if (-not (Test-Path $MainDir)) { throw "Directory not found: $MainDir" }

        Move-Item -Path $UpdaterExe -Destination $MainDir -Force

        # 检查并打印 Updater 大小
        $size = (Get-Item (Join-Path $MainDir "Updater.exe")).Length / 1MB
        $sizeStr = "{0:N2} MB" -f $size
        Write-Host "OK: Updater.exe moved. Size: $sizeStr (Much smaller!)" -ForegroundColor Green
    } else {
        throw "Error: Generated Updater.exe not found."
    }

    Write-Host "`n------------------------------------------"
    Write-Host "BUILD SUCCESS!" -ForegroundColor Green
    Write-Host "Output Folder: $MainDir" -ForegroundColor White
}
catch {
    Write-Host "`nBUILD FAILED: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    Write-Host "`nPress Enter to exit..."
    if ($Host.Name -eq 'ConsoleHost') { $null = Read-Host }
}
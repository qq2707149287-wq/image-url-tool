@echo off
echo ===================================================
echo   正在查找占用端口 8000 的僵尸进程...
echo ===================================================

for /f "tokens=5" %%a in ('netstat -aon ^| findstr "8000"') do (
    echo 发现目标 PID: %%a
    taskkill /f /pid %%a
    if errorlevel 0 (
        echo [OK] 进程 %%a 已成功终止
    ) else (
        echo [Error] 无法终止进程 %%a
    )
    goto :done
)

echo [Info] 未发现占用端口 8000 的进程
:done
echo ===================================================
echo   清理完成
echo ===================================================
pause

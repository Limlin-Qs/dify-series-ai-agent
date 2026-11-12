@echo off
chcp 65001 >nul
title 项目启动器
color 0B

:MENU
cls
echo ================================================
echo            个人项目一键启动器 v1.0
echo ================================================
echo.
echo   [1] PrivaSceFlow   私人流程优化（前端+后端）
echo   [2] 琳煦垚考试测评系统（前端+后端）
echo   [3] 创新项目查重系统（一键前后端）
echo   [4] Personal IP OS（Docker生产栈）
echo   [5] MatrixEye 监控平台（后端+前端）
echo   [6] Virtual-Service 电商平台（前端）
echo   [7] AlinOnline 海外站（前端）
echo   [8] 常用组合：PrivaSceFlow + 琳煦垚 + 查重
echo   [0] 退出
echo.
echo ================================================
set /p choice=请输入编号回车： 

if "%choice%"=="1" goto SCEFLOW
if "%choice%"=="2" goto EXAM
if "%choice%"=="3" goto DUPCHECK
if "%choice%"=="4" goto IPOS
if "%choice%"=="5" goto MATRIXEYE
if "%choice%"=="6" goto VIRTUAL
if "%choice%"=="7" goto ALIN
if "%choice%"=="8" goto COMBO
if "%choice%"=="0" exit /b
goto MENU

:: ---------- 1 PrivaSceFlow ----------
:SCEFLOW
start "PrivaSceFlow-后端" cmd /k "cd /d D:\PrivaSceFlow\backend && npm run dev"
timeout /t 3 /nobreak >nul
start "PrivaSceFlow-前端" cmd /k "cd /d D:\PrivaSceFlow\frontend && npm run dev"
echo PrivaSceFlow 已启动（两个窗口）
pause
goto MENU

:: ---------- 2 琳煦垚 ----------
:EXAM
start "琳煦垚-后端" cmd /k "cd /d D:\LinXuyao-Exam-System\backend && npm run start:dev"
timeout /t 3 /nobreak >nul
start "琳煦垚-前端" cmd /k "cd /d D:\LinXuyao-Exam-System\frontend && npm run dev"
echo 琳煦垚已启动（两个窗口）
pause
goto MENU

:: ---------- 3 查重系统 ----------
:DUPCHECK
start "查重系统-前后端" cmd /k "cd /d D:\Innovation-Project-Duplication-Check-Tool && npm run dev"
echo 查重系统已启动（concurrently单窗口）
pause
goto MENU

:: ---------- 4 Personal IP OS ----------
:IPOS
start "IP OS-Docker栈" cmd /k "cd /d D:\Personal IP OS && docker compose -f docker-compose.prod.yml up -d && docker compose -f docker-compose.prod.yml ps"
echo IP OS Docker栈已启动（窗口内可见容器状态）
pause
goto MENU

:: ---------- 5 MatrixEye ----------
:MATRIXEYE
start "MatrixEye-后端" cmd /k "cd /d D:\MatrixEye\backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "MatrixEye-前端" cmd /k "cd /d D:\MatrixEye\frontend && npm run dev"
echo MatrixEye已启动（两个窗口）
echo 注意：后端uvicorn若未装在全局Python，需先激活对应venv再运行
pause
goto MENU

:: ---------- 6 Virtual-Service ----------
:VIRTUAL
start "VirtualService-前端" cmd /k "cd /d D:\Virtual-Service\vs_frontend && npm run serve"
echo Virtual-Service前端已启动
echo 注意：Spring Boot后端需在IDE或另开窗口 mvn spring-boot:run（模块名待确认）
pause
goto MENU

:: ---------- 7 AlinOnline ----------
:ALIN
start "AlinOnline-前端" cmd /k "cd /d D:\AlinOnline\frontend && npm run serve"
echo AlinOnline前端已启动（含openssl-legacy-provider，Node17+兼容）
echo 注意：Java后端启动方式见项目docs，未纳入本启动器
pause
goto MENU

:: ---------- 8 常用组合 ----------
:COMBO
start "PrivaSceFlow-后端" cmd /k "cd /d D:\PrivaSceFlow\backend && npm run dev"
start "琳煦垚-后端" cmd /k "cd /d D:\LinXuyao-Exam-System\backend && npm run start:dev"
timeout /t 3 /nobreak >nul
start "PrivaSceFlow-前端" cmd /k "cd /d D:\PrivaSceFlow\frontend && npm run dev"
start "琳煦垚-前端" cmd /k "cd /d D:\LinXuyao-Exam-System\frontend && npm run dev"
start "查重系统-前后端" cmd /k "cd /d D:\Innovation-Project-Duplication-Check-Tool && npm run dev"
echo 常用组合已启动（5个窗口）
pause
goto MENU

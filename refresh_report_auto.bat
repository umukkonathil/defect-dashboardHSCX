@echo off
echo.
echo  ================================================
echo   Jira Defect Dashboard - Daily Refresh (Auto)
echo  ================================================
echo.

cd /d "%~dp0"

:: Step 0 - Archive previous CSV to Datafile folder
if exist "Jira_latest.csv" (
    if not exist "Datafile" mkdir Datafile
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
    set archive=Datafile\Jira_latest_%dt:~4,2%%dt:~6,2%%dt:~0,4%.csv
    copy /y "Jira_latest.csv" "%archive%" >nul
    echo  [0/4] Archived previous CSV to %archive%
)

:: Step 1 - Fetch latest issues from Jira
echo  [1/4] Fetching latest issues from Jira API...
python fetch_jira.py
if %errorlevel% neq 0 (
    echo  ERROR: Jira fetch failed. Check your .env token and internet connection.
    pause
    exit /b 1
)

:: Step 2 - Generate report
echo  [2/5] Generating dashboard from Jira_latest.csv...
python gen_report.py
if %errorlevel% neq 0 (
    echo  ERROR: Report generation failed.
    pause
    exit /b 1
)

:: Step 3 - Push to GitHub
echo  [3/5] Pushing to GitHub...
git add "HS CX-Defect.html"
git commit -m "Dashboard refresh - %date%"
git push origin main
if %errorlevel% neq 0 (
    echo  WARNING: GitHub push failed. Check your internet connection.
    pause
    exit /b 1
)

:: Step 4 - Open the live URL
echo  [4/5] Done! Opening live dashboard...
echo.
echo  Live URL:
echo  https://umukkonathil.github.io/defect-dashboardHSCX/HS%%20CX-Defect.html
echo.
start https://umukkonathil.github.io/defect-dashboardHSCX/HS%%20CX-Defect.html

timeout /t 3 >nul

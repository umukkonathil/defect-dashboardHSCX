@echo off
echo.
echo  ================================================
echo   Jira Defect Dashboard - Daily Refresh (Auto)
echo  ================================================
echo.

cd /d "%~dp0"

:: Step 1 - Fetch latest issues from Jira
echo  [1/4] Fetching latest issues from Jira API...
python fetch_jira.py
if %errorlevel% neq 0 (
    echo  ERROR: Jira fetch failed. Check your .env token and internet connection.
    pause
    exit /b 1
)

:: Step 2 - Generate report
echo  [2/4] Generating dashboard from Jira_latest.csv...
python gen_report.py
if %errorlevel% neq 0 (
    echo  ERROR: Report generation failed.
    pause
    exit /b 1
)

:: Step 3 - Push to GitHub
echo  [3/4] Pushing to GitHub...
git add "HS CX-Defect.html"
git commit -m "Dashboard refresh - %date%"
git push origin main
if %errorlevel% neq 0 (
    echo  WARNING: GitHub push failed. Check your internet connection.
    pause
    exit /b 1
)

:: Step 4 - Open the live URL
echo  [4/4] Done! Opening live dashboard...
echo.
echo  Live URL:
echo  https://umukkonathil.github.io/defect-dashboardHSCX/HS%%20CX-Defect.html
echo.
start https://umukkonathil.github.io/defect-dashboardHSCX/HS%%20CX-Defect.html

timeout /t 3 >nul

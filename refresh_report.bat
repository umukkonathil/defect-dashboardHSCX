@echo off
echo.
echo  ================================================
echo   Jira Defect Dashboard - Daily Refresh
echo  ================================================
echo.

cd /d "%~dp0"

:: Step 1 - Check CSV exists
if not exist "Jira_latest.csv" (
    echo  ERROR: Jira_latest.csv not found in this folder!
    echo  Please drop your Jira export here and try again.
    echo.
    pause
    exit /b 1
)

:: Step 2 - Generate report
echo  [1/3] Generating report from Jira_latest.csv...
python gen_report.py
if %errorlevel% neq 0 (
    echo  ERROR: Report generation failed.
    pause
    exit /b 1
)

:: Step 3 - Push to GitHub
echo  [2/3] Pushing to GitHub...
git add jira_latest_report.html
git commit -m "Dashboard refresh - %date%"
git push origin main
if %errorlevel% neq 0 (
    echo  WARNING: GitHub push failed. Check your internet connection.
    pause
    exit /b 1
)

:: Step 4 - Open the live URL
echo  [3/3] Done! Opening live dashboard...
echo.
echo  Live URL:
echo  https://umukkonathil.github.io/defect-dashboardHSCX/jira_latest_report.html
echo.
start https://umukkonathil.github.io/defect-dashboardHSCX/jira_latest_report.html

timeout /t 3 >nul

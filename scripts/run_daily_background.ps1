Set-Location "D:\Projects\Global_Net_Net_Scanner"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "logs\scheduled_daily_$ts.log"
& "D:\Projects\Global_Net_Net_Scanner\.venv\Scripts\python.exe" main.py daily *>> $log

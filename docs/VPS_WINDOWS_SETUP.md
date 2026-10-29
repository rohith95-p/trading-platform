# Running Ultra Core on an AWS VPS (Windows)

The MetaTrader5 Python package only works on **Windows**. On a Linux server
`import MetaTrader5` fails, so the VPS must be a **Windows Server 2022** EC2
instance (t3.medium or bigger: 2 vCPU / 4 GB RAM; MT5 + Python need ~1.5 GB).

Connect with Remote Desktop (EC2 console -> Connect -> RDP client -> get password).
Run everything below in **PowerShell as Administrator** on the VPS.

## 1. Install Python 3.11 and Git

```powershell
New-Item -ItemType Directory -Force C:\setup | Out-Null
Invoke-WebRequest https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile C:\setup\python.exe
Start-Process C:\setup\python.exe -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
Invoke-WebRequest https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe -OutFile C:\setup\git.exe
Start-Process C:\setup\git.exe -ArgumentList "/VERYSILENT /NORESTART" -Wait
```

Close and reopen PowerShell so `python` and `git` are on PATH, then check:

```powershell
python --version
git --version
```

## 2. Clone the project from GitHub

The repo is `rohith95-p/trading-platform`. If it is private, Git asks for a
username and password: use your GitHub username and a **Personal Access Token**
(GitHub -> Settings -> Developer settings -> Fine-grained tokens, read access to this repo).

```powershell
New-Item -ItemType Directory -Force C:\projects | Out-Null
git clone https://github.com/rohith95-p/trading-platform.git C:\projects\ultra_core
cd C:\projects\ultra_core
```

`start_ultra_core.bat` expects exactly `C:\projects\ultra_core` and a `venv` folder.

## 3. Python environment

```powershell
cd C:\projects\ultra_core
python -m venv venv
.\venv\Scripts\python -m pip install --upgrade pip
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python -c "import MetaTrader5, numpy, pandas; print('imports ok')"
.\venv\Scripts\python -m pytest -p no:cacheprovider -o addopts="" -q
```

## 4. Secrets file (never commit it)

`.env.local` is not in Git. Copy it from your PC: open it in Notepad on the PC,
copy all, then on the VPS:

```powershell
notepad C:\projects\ultra_core\.env.local
```

paste, save. If the MT5 account number on the VPS is not the default one, add a
line `MT5_LOGIN=<your account number>`.

## 5. MetaTrader 5

1. Download the Exness MT5 terminal from your Exness Personal Area and install it.
2. Log in to the trading account (File -> Login to Trade Account), tick "Save password".
3. Tools -> Options -> Expert Advisors -> tick **Allow algorithmic trading**.
4. Add XAUUSD (your `ULTRA_SYMBOL`) to Market Watch.

## 6. Keep it running

Never sleep or turn off the screen:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

Start the bot when Windows logs in:

```powershell
$a = New-ScheduledTaskAction -Execute "C:\projects\ultra_core\start_ultra_core.bat"
$t = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "UltraCore" -Action $a -Trigger $t -RunLevel Highest
```

Start it now:

```powershell
Start-ScheduledTask -TaskName "UltraCore"
```

When you leave, **close the Remote Desktop window (X)** -- do not "Sign out".
Signing out kills MT5 and the bot; closing the window keeps them running.

## 7. Update to the latest code

The STOP file **closes all open bot trades** and halts the bot, so only update
when no trade is open (e.g. on the weekend).

```powershell
cd C:\projects\ultra_core
New-Item STOP -ItemType File   # flattens bot trades and halts
git pull
.\venv\Scripts\pip install -r requirements.txt
Remove-Item STOP
Start-ScheduledTask -TaskName "UltraCore"
```

## Troubleshooting

- `ModuleNotFoundError: No module named 'MetaTrader5'` -> you are on Linux, or not
  using the venv (`.\venv\Scripts\python`).
- `ModuleNotFoundError: No module named 'src'` -> run from `C:\projects\ultra_core`.
- Bot says "wrong account" -> set `MT5_LOGIN` in `.env.local`.

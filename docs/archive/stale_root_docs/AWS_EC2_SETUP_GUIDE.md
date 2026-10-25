# AWS EC2 Setup Guide - Ultra Core Trading Bot

## Quick Setup (Using GitHub)

Instead of uploading zip files, we'll clone directly from GitHub!

---

## Prerequisites

1. **GitHub Repository**
   - First, push your ultra_core code to GitHub
   - Make it private (recommended for trading bots)
   - Get the clone URL

2. **AWS EC2 Instance**
   - Windows Server 2022
   - t3.small or better (t2.micro is too slow)
   - Security group: RDP (port 3389) open
   - Key pair for RDP access

---

## Step 1: Push to GitHub (Do This First)

**On your local machine:**

```bash
cd c:\projects\ultra_core

# Initialize git if not already
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - Ultra Core trading bot"

# Create GitHub repo and push
# (Follow GitHub's instructions to create a new private repo)
git remote add origin https://github.com/YOUR_USERNAME/ultra_core.git
git branch -M main
git push -u origin main
```

**Important files to add to `.gitignore`:**

```gitignore
# Secrets
.env.local
.env

# MT5 data
*.ex5
*.dll

# Logs
logs/
*.log

# Python
__pycache__/
*.pyc
.pytest_cache/

# Temporary
*.tmp
temp/

# OS
.DS_Store
Thumbs.db
```

---

## Step 2: Launch EC2 Instance

**Via AWS Console:**

1. Go to EC2 → Launch Instance
2. Name: `ultra-core-trading-bot`
3. AMI: **Windows Server 2022 Base**
4. Instance type: **t3.small** (recommended) or t2.micro (slower)
5. Key pair: Create new or use existing
6. Security group: Allow RDP (3389)
7. Storage: 30 GB (default)
8. Launch!

**Wait 2-3 minutes for instance to start.**

---

## Step 3: Connect via RDP

**Get password:**

```bash
# Wait 4 minutes after launch, then:
aws ec2 get-password-data \
  --instance-id i-YOUR-INSTANCE-ID \
  --priv-launch-key ultra-core-key.pem \
  --region ap-south-1
```

**Connect:**
1. Open Remote Desktop Connection
2. Computer: [EC2 Public IP]
3. Username: `Administrator`
4. Password: [from above command]

---

## Step 4: Run Automated Setup

**Inside the EC2 RDP session:**

### Option A: One-Line Install (Recommended)

Open **PowerShell as Administrator** and run:

```powershell
# Download and run setup script
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/YOUR_USERNAME/ultra_core/main/scripts/aws_ec2_setup.ps1" -OutFile "$env:TEMP\setup.ps1"
powershell -ExecutionPolicy Bypass -File "$env:TEMP\setup.ps1"
```

### Option B: Manual Setup

**If one-line doesn't work:**

```powershell
# 1. Install Chocolatey
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 2. Install Git and Python
choco install git python311 -y
refreshenv

# 3. Clone repository
cd $env:USERPROFILE
git clone https://github.com/YOUR_USERNAME/ultra_core.git
cd ultra_core

# 4. Install dependencies
pip install -r requirements.txt

# 5. Download and install MT5
$url = "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\mt5setup.exe"
Start-Process "$env:TEMP\mt5setup.exe" -ArgumentList "/auto" -Wait
```

---

## Step 5: Configure Environment

**Create `.env.local` file:**

```powershell
cd $env:USERPROFILE\ultra_core

# Create .env.local with your settings
@"
# Telegram Alerts
ULTRA_ALERT_TELEGRAM_TOKEN=<YOUR_TELEGRAM_BOT_TOKEN>
ULTRA_ALERT_TELEGRAM_CHAT=6536063986

# Add other secrets as needed
"@ | Out-File -FilePath .env.local -Encoding UTF8
```

---

## Step 6: Setup MetaTrader 5

1. **Open MT5** (should be installed from setup script)
2. **Login to Exness:**
   - Server: `Exness-MT5Trial11`
   - Login: `198874999`
   - Password: [your password]
3. **Enable XAUUSDm:**
   - View → Symbols (Ctrl+U)
   - Search "XAUUSD"
   - Show symbol "XAUUSDm"
4. **Enable Algo Trading:**
   - Tools → Options → Expert Advisors
   - Check "Allow automated trading"
   - Check "Allow DLL imports"

---

## Step 7: Test the Bot

**Run pre-flight check:**

```powershell
cd $env:USERPROFILE\ultra_core
python scripts/pre_flight_check.py
```

**Expected output:**
```
🚀 ALL SYSTEMS GO!
   Ready to start trading Monday morning!
```

---

## Step 8: Start Trading

**When market opens (Monday):**

```powershell
cd $env:USERPROFILE\ultra_core
python -m src.main_loop
```

**To run in background (keep running after you disconnect RDP):**

```powershell
# Install NSSM (Non-Sucking Service Manager)
choco install nssm -y

# Create Windows service
nssm install UltraCore "C:\Python311\python.exe" "-m src.main_loop"
nssm set UltraCore AppDirectory "$env:USERPROFILE\ultra_core"
nssm start UltraCore

# Check status
nssm status UltraCore
```

---

## Step 9: Monitor

**Check logs:**

```powershell
# View today's trades
Get-Content "$env:USERPROFILE\ultra_core\logs\trades\$(Get-Date -Format 'yyyy-MM-dd').jsonl" -Wait

# Check if bot is running
Get-Process | Where-Object {$_.ProcessName -like "*python*"}
```

**Via Telegram:**
- You'll get alerts for every trade
- Daily summaries at 11:30 PM IST

---

## Updating the Bot (Pull Latest Changes)

**To update bot with new code:**

```powershell
cd $env:USERPROFILE\ultra_core

# Stop bot if running as service
nssm stop UltraCore

# Pull latest changes
git pull origin main

# Restart
nssm start UltraCore

# Or run manually
python -m src.main_loop
```

---

## Troubleshooting

### Bot Not Starting?

```powershell
# Check Python path
python --version

# Check MT5 connection
python -c "import MetaTrader5 as mt5; print('MT5 OK' if mt5.initialize() else 'MT5 FAIL')"

# Check logs
Get-Content logs\alerts.log -Tail 50
```

### MT5 Not Connecting?

1. Make sure MT5 is open
2. Check you're logged in
3. Enable algo trading in settings
4. Restart MT5

### No Trades Executing?

1. Check if market is open
2. Run: `python scripts/check_market_status.py`
3. Check D1 bias gate (might be blocking)
4. Review logs: `logs\trades\[date].jsonl`

---

## Cost Estimate

**EC2 t3.small (recommended):**
- Price: ~$0.023/hour
- Monthly: ~$16.80
- With Windows: ~$25/month total

**EC2 t2.micro (slower but cheaper):**
- Price: ~$0.012/hour
- Monthly: ~$8.76
- With Windows: ~$15/month total
- **Note:** Might be laggy for MT5

**Recommendation:** Use t3.small for smooth operation

---

## Security Best Practices

1. **Keep repository private** on GitHub
2. **Never commit `.env.local`** (add to .gitignore)
3. **Use strong passwords** for EC2 and MT5
4. **Restrict RDP access** (use your IP only in security group)
5. **Enable CloudWatch logs** (optional) for monitoring
6. **Backup .env.local** somewhere safe

---

## Benefits of GitHub Method

✅ **No zip uploads** (faster setup)  
✅ **Easy updates** (just `git pull`)  
✅ **Version control** (track changes)  
✅ **Backup** (code is on GitHub)  
✅ **Multi-server** (clone to multiple EC2 instances)  
✅ **Collaboration** (if you add team members later)  

---

## Quick Command Reference

```powershell
# Clone repo
git clone https://github.com/YOUR_USERNAME/ultra_core.git

# Update code
cd ultra_core
git pull origin main

# Check status
python scripts/pre_flight_check.py

# Start bot
python -m src.main_loop

# Run as service
nssm install UltraCore "C:\Python311\python.exe" "-m src.main_loop"
nssm start UltraCore
nssm status UltraCore
nssm stop UltraCore

# Check logs
Get-Content logs\trades\$(Get-Date -Format 'yyyy-MM-dd').jsonl -Wait

# Weekly review
python scripts/weekly_review.py
```

---

## Next Steps After Setup

1. **Test on demo** for 1-2 weeks
2. **Monitor via Telegram** daily
3. **Review weekly reports** every Sunday
4. **Switch to live account** when confident
5. **Scale up** (add more capital or instances)

---

**Ready to set this up? Let me know if you need help with any step!** 🚀

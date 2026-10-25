import yfinance as yf
import pandas as pd
import json

tickers = ["GC=F", "SI=F", "DX-Y.NYB", "^TNX", "CL=F", "^VIX"]
data = {}
for ticker in tickers:
    t = yf.Ticker(ticker)
    df = t.history(period="5d")
    if not df.empty:
        # Convert index to strings for json serialization
        df.index = df.index.strftime('%Y-%m-%d')
        # We only need the close prices
        data[ticker] = df['Close'].to_dict()
    else:
        data[ticker] = None

with open("market_data.json", "w") as f:
    json.dump(data, f, indent=2)
print("Data fetched successfully")

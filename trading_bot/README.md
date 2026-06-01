# Binance Futures Testnet Trading Bot

A lightweight Python CLI application to place **Market**, **Limit**, and **Stop-Market** orders on [Binance Futures Testnet (USDT-M)](https://testnet.binancefuture.com).

---

## Features

-  Market orders (BUY / SELL)
-  Limit orders (BUY / SELL)
-  **Bonus:** Stop-Market orders
-  CLI with `argparse` (symbol, side, type, quantity, price flags)
-  Input validation with clear error messages
-  Structured logging to timestamped log files
-  Full exception handling (API errors, network failures, bad input)

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance API client (HMAC-SHA256 signing)
│   ├── orders.py          # Order placement logic
│   ├── validators.py      # Input validation
│   └── logging_config.py  # File + console logging setup
├── logs/                  # Auto-created; stores timestamped .log files
├── cli.py                 # CLI entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Create a Binance Futures Testnet Account

1. Go to **https://testnet.binancefuture.com**
2. Click **"Log In with GitHub"** to register / sign in
3. Navigate to **"API Keys"** (top-right profile menu)
4. Click **"Generate Key"** — copy your **API Key** and **Secret Key**

>  The secret is shown only once. Save it immediately.

### 2. Configure Credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials:

```
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

> Never commit your `.env` file to version control.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Python 3.8+ is required.

---

## Usage

### Place a Market Order

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### Place a Limit Order

```bash
python cli.py --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.001 --price 30000
```

### Place a Stop-Market Order *(bonus)*

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 28000
```

### Show Help

```bash
python cli.py --help
```

---

## Example Output

```
INFO     | Logging initialised → logs/trading_bot_20240601_143022.log

┌── Order Request Summary ──────────────────────────────────
│  symbol         : BTCUSDT
│  side           : BUY
│  order_type     : LIMIT
│  quantity       : 0.001
│  price          : 30000.0
└──────────────────────────────────────────────────────────

┌── Order Response ──────────────────────────────────────────
│  orderId        : 3951475642
│  symbol         : BTCUSDT
│  status         : NEW
│  side           : BUY
│  type           : LIMIT
│  origQty        : 0.001
│  executedQty    : 0
│  avgPrice       : 0.00000
│  price          : 30000
└──────────────────────────────────────────────────────────

[SUCCESS] ✓ Order placed successfully.
```

---

## Logging

Each run creates a new log file: `logs/trading_bot_YYYYMMDD_HHMMSS.log`

The log captures:
- Validated input parameters
- Full API request details (params, minus credentials)
- Full API response
- All errors and exceptions

---

## Assumptions

- All orders target **Binance Futures Testnet (USDT-M)** only; the base URL is hardcoded to `https://testnet.binancefuture.com`.
- `timeInForce` for LIMIT orders defaults to **GTC** (Good Till Cancelled).
- Quantity precision follows BTCUSDT testnet rules (`0.001` BTC minimum works in testing).
- API credentials are loaded from `.env` via `python-dotenv`; they can also be set as real environment variables.
- No retry logic is implemented; transient network failures surface as errors to the caller.

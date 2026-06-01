"""Central configuration constants for the trading bot."""

# ── Binance Futures Testnet ───────────────────────────────────────────────────
BASE_URL = "https://testnet.binancefuture.com"
ORDER_ENDPOINT = "/fapi/v1/order"

# ── Default request settings ──────────────────────────────────────────────────
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_TIME_IN_FORCE = "GTC"   # Good Till Cancelled

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = "logs"
LOG_DATE_FORMAT = "%Y%m%d_%H%M%S"

# ── Validation ────────────────────────────────────────────────────────────────
VALID_SIDES = frozenset({"BUY", "SELL"})
VALID_ORDER_TYPES = frozenset({"MARKET", "LIMIT", "STOP_MARKET"})

# ── OpenRouter LLM ────────────────────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL    = "openai/gpt-oss-120b:free"
LLM_TEMPERATURE     = 0          # deterministic JSON extraction
LLM_MAX_TOKENS      = 256        # order params are small

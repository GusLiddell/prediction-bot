"""
Executor layer: places orders on Kalshi based on trade recommendations.
Set DRY_RUN=true in .env to log orders without actually placing them.
"""
import os
import time
import base64
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import httpx
from db.database import get_conn

DRY_RUN  = os.getenv("DRY_RUN", "true").lower() == "true"
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

# Cost per contract in cents (Kalshi contracts settle at $1)
CONTRACT_COST_CENTS = int(os.getenv("CONTRACT_COST_CENTS", "10"))  # ~10¢ per contract


def _load_key():
    path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalshi_private.pem")
    key_path = Path(path) if Path(path).is_absolute() else Path(__file__).parent / path
    with open(key_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _sign(private_key, ts: int, method: str, path: str) -> str:
    msg = f"{ts}{method}{path}".encode()
    sig = private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def _auth_headers(private_key, method: str, path: str) -> dict:
    ts = int(time.time() * 1000)
    return {
        "KALSHI-ACCESS-KEY": os.getenv("KALSHI_API_KEY", ""),
        "KALSHI-ACCESS-TIMESTAMP": str(ts),
        "KALSHI-ACCESS-SIGNATURE": _sign(private_key, ts, method, path),
        "Content-Type": "application/json",
    }


def place_order(trade: dict) -> dict:
    """
    Place a single market order on Kalshi.
    trade = {market_id, side, suggested_contracts, ...}
    Returns the API response or a dry-run summary.
    """
    market_id = trade["market_id"]
    side      = trade["side"]          # "yes" or "no"
    count     = trade.get("suggested_contracts", 1)

    if DRY_RUN:
        print(f"[executor] DRY RUN — would buy {count}x {side.upper()} on {market_id} | {trade['title']}")
        print(f"           Reason: {trade.get('reasoning', '')}")
        _log_trade(trade, count, "dry_run")
        return {"dry_run": True, "market_id": market_id, "side": side, "count": count}

    private_key = _load_key()
    path = "/trade-api/v2/portfolio/orders"
    headers = _auth_headers(private_key, "POST", path)

    payload = {
        "ticker":  market_id,
        "action":  "buy",
        "type":    "market",
        "side":    side,
        "count":   count,
    }

    resp = httpx.post(f"{BASE_URL}/portfolio/orders", headers=headers, json=payload, timeout=15)
    if resp.status_code == 201:
        print(f"[executor] Order placed: {count}x {side.upper()} on {market_id}")
        _log_trade(trade, count, "filled")
        return resp.json()
    else:
        print(f"[executor] Order FAILED ({resp.status_code}): {resp.text}")
        _log_trade(trade, count, "failed")
        return {"error": resp.text, "market_id": market_id}


def _log_trade(trade: dict, count: int, status: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO trade_log (source, market_id, title, side, contracts, yes_price,
                                   confidence, reasoning, score, dry_run, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "kalshi",
            trade["market_id"],
            trade.get("title", ""),
            trade["side"],
            count,
            None,
            trade.get("confidence"),
            trade.get("reasoning"),
            trade.get("_score"),
            1 if DRY_RUN else 0,
            status,
        ))


def execute(trades: list[dict]) -> list[dict]:
    """Execute all recommended trades. Returns list of results."""
    if not trades:
        print("[executor] No trades to execute.")
        return []

    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"[executor] Executing {len(trades)} trade(s) [{mode}]")

    results = []
    for trade in trades:
        result = place_order(trade)
        results.append(result)
        time.sleep(0.5)  # avoid rate limits

    return results

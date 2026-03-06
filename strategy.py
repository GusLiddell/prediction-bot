"""
Rule-based strategy layer — no API calls, runs completely free.

Scoring rules (each adds points toward a trade recommendation):
  - Price close to 50%     → high uncertainty = opportunity
  - Closing within 7 days  → time pressure = market should be efficient
  - High liquidity         → easier to enter/exit
  - High volume            → active market, tighter spreads
  - Price skew             → bias toward underdog (contrarian edge)
"""
import os
from datetime import datetime, timezone
from db.database import get_conn

# ── Config ────────────────────────────────────────────────────────────────────

MIN_LIQUIDITY   = float(os.getenv("MIN_LIQUIDITY",   "5000"))
MIN_VOLUME      = float(os.getenv("MIN_VOLUME",      "10000"))
MAX_TRADES      = int(os.getenv("MAX_TRADES",        "3"))

# Price band for "contested" markets
PRICE_MIN       = float(os.getenv("PRICE_MIN",       "0.25"))
PRICE_MAX       = float(os.getenv("PRICE_MAX",       "0.75"))

# Only trade markets closing within this many days
MAX_DAYS_TO_CLOSE = int(os.getenv("MAX_DAYS_TO_CLOSE", "365"))


# ── Candidate fetch ───────────────────────────────────────────────────────────

def get_candidates(source: str = "kalshi") -> list[dict]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                m.source, m.market_id, m.title, m.end_date, m.url,
                s.yes_price, s.no_price, s.volume, s.liquidity
            FROM markets m
            JOIN (
                SELECT market_id, source, yes_price, no_price, volume, liquidity,
                       ROW_NUMBER() OVER (PARTITION BY source, market_id ORDER BY timestamp DESC) rn
                FROM snapshots
            ) s ON m.source = s.source AND m.market_id = s.market_id AND s.rn = 1
            WHERE m.source     = ?
              AND m.is_active  = 1
              AND s.liquidity >= ?
              AND s.volume    >= ?
              AND s.yes_price IS NOT NULL
              AND s.yes_price  > 0.02
              AND s.yes_price  < 0.98
            ORDER BY s.liquidity DESC
        """, (source, MIN_LIQUIDITY, MIN_VOLUME)).fetchall()
    return [dict(r) for r in rows]


# ── Scoring ───────────────────────────────────────────────────────────────────

def _days_to_close(end_date_str: str | None) -> float | None:
    if not end_date_str:
        return None
    try:
        end = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = (end - datetime.now(timezone.utc)).total_seconds() / 86400
        return delta
    except ValueError:
        return None


def _score(market: dict) -> tuple[float, str, str]:
    """
    Returns (score, side, reasoning).
    Higher score = better opportunity.
    """
    yes = market["yes_price"]
    no  = 1 - yes
    liq = market["liquidity"] or 0
    vol = market["volume"] or 0
    dtc = _days_to_close(market.get("end_date"))

    score = 0.0
    reasons = []

    # 1. Closing timeline (sooner = more points, but don't exclude long-horizon)
    if dtc is not None:
        if dtc < 0:
            return -1.0, "yes", "already closed"  # skip expired
        elif dtc <= 1:
            score += 3.0; reasons.append("closes within 24h")
        elif dtc <= 7:
            score += 2.0; reasons.append(f"closes in {dtc:.0f}d")
        elif dtc <= 30:
            score += 1.5; reasons.append(f"closes in {dtc:.0f}d")
        elif dtc <= MAX_DAYS_TO_CLOSE:
            score += 0.5; reasons.append(f"closes in {dtc:.0f}d")
        else:
            return -1.0, "yes", "too far out"  # skip

    # 2. Price near 50% (maximum uncertainty)
    distance_from_50 = abs(yes - 0.5)
    score += max(0, 2.0 - distance_from_50 * 6)

    # 3. Liquidity bonus
    if liq >= 100_000:
        score += 2.0; reasons.append(f"liq ${liq:,.0f}")
    elif liq >= 20_000:
        score += 1.0

    # 4. Volume bonus
    if vol >= 500_000:
        score += 1.5
    elif vol >= 100_000:
        score += 0.5

    # 5. Pick side: back the underdog slightly (contrarian — underdogs are
    #    systematically underpriced in prediction markets)
    if yes < 0.5:
        side = "yes"
        reasoning = f"yes at {yes:.0%} looks underpriced; {', '.join(reasons)}"
    else:
        side = "no"
        reasoning = f"no at {no:.0%} looks underpriced; {', '.join(reasons)}"

    return score, side, reasoning


# ── Main entry point ──────────────────────────────────────────────────────────

def run(source: str = "kalshi") -> list[dict]:
    candidates = get_candidates(source)
    print(f"[strategy] {len(candidates)} candidates from {source}")

    scored = []
    for m in candidates:
        score, side, reasoning = _score(m)
        if score <= 0:
            continue
        scored.append({
            "market_id":          m["market_id"],
            "title":              m["title"],
            "side":               side,
            "reasoning":          reasoning,
            "confidence":         "high" if score >= 5 else "medium" if score >= 3 else "low",
            "suggested_contracts": 5 if score >= 5 else 3 if score >= 3 else 1,
            "_score":             score,
        })

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x["_score"], reverse=True)
    trades = scored[:MAX_TRADES]

    print(f"[strategy] {len(trades)} trade(s) recommended")
    return trades

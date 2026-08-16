# Upstox API research notes — verified 2026-08-16

Sources are the current official documentation: [authentication](https://upstox.com/developer/api-documentation/authentication/), [instrument master](https://upstox.com/developer/api-documentation/instruments/), [historical candles V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/), [Market Data Feed V3](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/), [orders V3](https://upstox.com/developer/api-documentation/v3/place-order/), [option chain](https://upstox.com/developer/api-documentation/get-pc-option-chain/), and [rate limits](https://upstox.com/developer/api-documentation/rate-limiting/).

## Confirmed integration choices

- OAuth is authorization-code flow. Login redirects to `https://api.upstox.com/v2/login/authorization/dialog`; code exchange is a form POST to `/v2/login/authorization/token`. The code is single-use and redirect URI must exactly match the developer-app registration.
- Use BOD JSON master and `instrument_key`, never `exchange_token`, for durable instrument identity. `exchange_token` can be recycled after expiry. Current implementation downloads the complete compressed JSON master and resolves active contracts from its fields. The current endpoint serves a raw `application/gzip` payload (no `Content-Encoding`), which the client explicitly decompresses.
- Historical REST uses V3 `/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date?}`. Daily data starts from 2000; intraday starts January 2022. One-to-15-minute queries are limited to one month, and longer minute intervals / hours to one quarter.
- India VIX key is `NSE_INDEX|India VIX`; global instruments can provide USD/INR, Brent and WTI indicators. This reduces—but does not eliminate—the need for an extra source for initial cross-asset research.
- Put/call option-chain API exists for a selected underlying/expiry, but specifically excludes MCX. Historical option-chain snapshots are not confirmed, so options premium backtests remain **DATA UNAVAILABLE** pending data validation.
- Feed V3 is a redirected `wss` connection with binary protobuf messages. Subscription messages are binary, and a client must decode using Upstox's provided protobuf schema. It sends a market-status message, then snapshot, then updates. Basic automatic websocket ping is documented. The project emits the documented binary subscription envelope and enforces stale/duplicate gating, but refuses to decode/connect until a current official `.proto` artifact is pinned.
- GitHub verification resolved the protobuf dependency: the [official Upstox Python SDK](https://github.com/upstox/upstox-python) version `2.28.0` carries `MarketDataFeedV3.proto` and `MarketDataStreamerV3`. The pinned SDK decoder is now used by `app/broker/upstox_feed.py`; raw `FeedResponse` messages become normalized `MarketTick` values for LTPC, full-feed and first-level-with-Greeks variants. It is market-data only and cannot place orders.
- V3 market-feed limits: two connections per user; combined subscription limits are 2,000 keys (LTPC individual 5,000; Greeks 3,000; full 2,000) with lower documented combined constraints for full mode (1,500). Implement subscriptions conservatively below the combined limits.
- Standard order requests are limited at 10/sec for regular algos (50/sec for SEBI-registered), 500/minute, 2,000/30 minutes. Other standard APIs are 50/sec, 500/minute, 2,000/30 minutes. Rate-limit behavior must be centralized before any execution work.
- V3 place-order endpoint is currently documented at `api-hft.upstox.com/v3/order/place`, with instrument validation, tags, optional slicing and market protection. It is intentionally not called by the Phase 2 code.
- Sandbox supports place/modify/cancel orders only; it cannot validate realistic paper P&L/data behavior. The system will maintain an independent paper-fill simulator.

## Gaps / constraints

1. There is no evidence yet of a historical tick feed or historical option-chain surface suitable for realistic options backtesting.
2. MCX option chain is not available through the documented PC option-chain endpoint.
3. Standard access token may require a daily authorization; the analytics token is described as generated once for market data/streaming, with additional access restrictions. Credential lifecycle needs a manual operational runbook.
4. Current local machine did not have system Python, Docker, or PostgreSQL CLI. A bundled Python 3.12 runtime was used to create `.venv`; Docker Compose configuration is provided but cannot be exercised here.

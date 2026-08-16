WebSocket API (Design)
======================

If the system is configured to provide real-time streaming, the WebSocket API follows this design. The backend currently has market streaming modules and a design for websocket authorization (Upstox). The following describes the expected socket protocol for a frontend.

Connection
----------
- URL (development): ws://localhost:8000/ws (TLS in production: wss://...)
- Authentication: Bearer token or session cookie. For Upstox streaming, the client first calls /auth/upstox/login -> Upstox returns a redirect to authorized websocket endpoint when requested via UpstoxClient.market_data_authorize_url(). This Upstox-specific flow is broker-facing; internal WebSocket should accept platform-level auth.

Subscription messages
---------------------
Client -> Server JSON messages to subscribe/unsubscribe:

Subscribe example:
{
  "action": "subscribe",
  "channels": ["tick:NSE_INDEX|Nifty 50", "signal", "order_events"],
  "request_id": "abcd-1234"
}

Unsubscribe example:
{
  "action": "unsubscribe",
  "channels": ["tick:NSE_INDEX|Nifty 50"],
  "request_id": "..."
}

Server -> Client message examples
--------------------------------
Market tick:
{
  "channel": "tick",
  "instrument_key": "NSE_INDEX|Nifty 50",
  "timestamp": "2026-08-16T09:24:00.123Z",
  "ltp": 22350.5,
  "bid": 22350.0,
  "ask": 22351.0,
  "volume": 1234
}

Signal update:
{
  "channel": "signal",
  "signal_id": "...",
  "symbol": "NIFTY",
  "signal": "BUY",
  "score": 0.73,
  "explanation": "Momentum + regime alignment",
  "timestamp": "2026-08-16T09:25:02.700Z"
}

Order event:
{
  "channel": "order_event",
  "order_id": "...",
  "status": "EXECUTED",
  "filled_qty": 1,
  "price": 22350.5,
  "timestamp": "2026-08-16T09:25:10.124Z"
}

Heartbeat and reconnect
-----------------------
- Server sends periodic heartbeat messages: {"channel":"heartbeat","timestamp":"..."}
- Clients should reconnect with exponential backoff on socket close and re-subscribe to channels.
- Messages may be sequence-numbered for de-duplication.

Stale-data handling
-------------------
- Each tick carries a timestamp. The client should treat data as stale if the timestamp is older than a configured threshold (e.g., 30s for index ticks, 120s for option chains).

Note: The current repository provides scaffolding and Upstox client helper methods for obtaining authorized Upstox websocket endpoints. The internal WS server is not yet implemented but should follow this message format to keep the frontend agnostic of backend internals.

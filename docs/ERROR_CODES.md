API Error Codes
================
This file lists canonical error codes returned by the backend, their meaning and suggested front-end handling.

Response envelope (error example)
---------------------------------
{
  "success": false,
  "data": null,
  "error": {
    "code": "RISK_LIMIT_BREACHED",
    "message": "Trade rejected: risk limit would be exceeded",
    "details": {"limit": 10000, "projected_margin": 12000}
  },
  "timestamp": "2026-08-16T14:20:03.508Z",
  "request_id": "..."
}

Common error codes
------------------
- AUTH_REQUIRED: Authentication required for the endpoint. Frontend should redirect to auth flow.
- BROKER_DISCONNECTED: Broker connection is down. Suggest retry and show broker status widget.
- MARKET_DATA_STALE: Market data older than tolerated threshold. Frontend should indicate stale data and disable order placement.
- INVALID_INSTRUMENT: Provided instrument key is unknown or invalid. Show validation error.
- INVALID_EXPIRY: Expiry is not valid for the requested underlying.
- INVALID_STRIKE: Strike is not valid for the requested option chain.
- INSUFFICIENT_CAPITAL: Not enough capital to place the requested order.
- MARGIN_LIMIT: Margin usage would exceed allowed limit.
- RISK_LIMIT_BREACHED: Strategy or portfolio risk budget would be exceeded.
- MAX_DRAWDOWN: Portfolio drawdown limit reached; trading disabled.
- KILL_SWITCH_ACTIVE: Global kill switch is active; immediately disable trade UI and show emergency dialog.
- RECONCILIATION_MISMATCH: Offline reconciliation detected mismatches; surface as audit log item.
- ORDER_REJECTED: Broker rejected order: inspect details.
- LIVE_MODE_NOT_CONFIRMED: Attempt to use LIVE endpoints without explicit confirmation.
- DATA_UNAVAILABLE: Requested historical or option-chain data not available for the requested period.

Guidance for front-end
----------------------
- Map codes to human-friendly localized messages.
- For severe errors (KILL_SWITCH_ACTIVE, LIVE_MODE_NOT_CONFIRMED) show blocking UI states and prevent trading operations.
- For recoverable errors (MARKET_DATA_STALE), show warnings and retry logic.

Extensibility
-------------
- Use the error.details object to show metrics or suggested corrective actions.
- Add codes for new domain-specific failures as needed and document them here.

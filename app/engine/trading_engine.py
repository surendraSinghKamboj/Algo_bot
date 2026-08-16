from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from app.broker.upstox_feed import MarketTick
from app.execution.paper import PaperExecutionEngine, PaperOrder, PaperLeg
from app.engine.hedge import compute_hedge_quantity
from app.engine.pipeline import TradePipeline
from app.portfolio.ledger import PositionLedger
from app.strategies.nifty import NiftyStrategy

from app.market.instrument_lookup import nearest_expiry_for_underlying, atm_strike_from_spot, resolve_option_by_strike, get_latest_tick_for_instrument
from app.data import storage

log = logging.getLogger(__name__)


class TradingEngine:
    """Orchestrates ticks -> strategy -> hedge -> risk -> paper execution -> ledger updates.

    Designed to be simple and deterministic for paper-trading and unit tests.
    """

    def __init__(self, *, strategy: Optional[NiftyStrategy] = None, pipeline: Optional[TradePipeline] = None, paper_engine: Optional[PaperExecutionEngine] = None, ledger: Optional[PositionLedger] = None, starting_cash: float = 500000.0):
        self.strategy = strategy or NiftyStrategy()
        self.paper_engine = paper_engine or PaperExecutionEngine(trading_mode="PAPER")
        self.pipeline = pipeline or TradePipeline(paper_engine=self.paper_engine)
        self.ledger = ledger or PositionLedger(starting_cash=starting_cash)
        self.starting_cash = starting_cash
        # Simple stateful snapshot of last market tick per instrument
        self.last_ticks: dict[str, MarketTick] = {}

    def handle_tick(self, tick: MarketTick) -> Optional[PaperOrder]:
        """Process a single MarketTick and possibly execute a paper trade.

        Returns the executed PaperOrder if one was placed, otherwise None.
        """
        # store last tick
        self.last_ticks[tick.instrument_key] = tick
        try:
            # Build a simple market snapshot expected by the Nifty strategy
            snapshot = {
                "NIFTY": float(tick.ltp),
                "India VIX": float(15.0),  # placeholder; real VIX should come from feed
            }
            # Generate strategy signal
            sig = self.strategy.generate_signal(snapshot)
            log.info("Strategy signal: %s score=%.3f reasons=%s", sig.action, sig.score, getattr(sig, 'reasons', None))

            # Persist signal if DB available
            try:
                from app.database.session import SessionLocal
                import uuid
                with SessionLocal() as session:
                    try:
                        storage.store_signal(session, strategy="NIFTY_HEDGED_V1", instrument_key=tick.instrument_key, action=sig.action, score=float(getattr(sig, 'score', 0.0)), explanation=str(getattr(sig, 'reasons', '')), payload=getattr(sig, 'payload', {}) or {})
                    except Exception:
                        session.rollback()
            except Exception:
                # DB not available or error; continue without persistence
                pass

            # If the strategy provided an option_structure payload, handle multi-leg flow here
            plan_payload = getattr(sig, "payload", None) or {}
            if isinstance(plan_payload, dict) and plan_payload.get("option_structure"):
                # dynamic option resolution and multi-leg execution
                try:
                    from app.database.session import SessionLocal
                    import uuid as _uuid
                    with SessionLocal() as session:
                        underlying_key = plan_payload.get("underlying_key") or tick.instrument_key
                        expiry_dt = nearest_expiry_for_underlying(session, underlying_key)
                        if not expiry_dt:
                            log.info("No expiry found for underlying %s; skipping option structure", underlying_key)
                            return None
                        spot = float(tick.ltp)
                        atm = atm_strike_from_spot(spot, strike_step=plan_payload.get("strike_step", 50))

                        structure = plan_payload.get("structure")
                        if structure == "BULL_CALL_SPREAD":
                            buy_strike = atm
                            sell_strike = Decimal(int(atm) + int(plan_payload.get("width", 200)))
                            buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, "CE")
                            sell_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, sell_strike, "CE")
                        elif structure == "BEAR_PUT_SPREAD":
                            sell_strike = atm
                            buy_strike = Decimal(int(atm) - int(plan_payload.get("width", 200)))
                            buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, "PE")
                            sell_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, sell_strike, "PE")
                        else:
                            log.info("Unsupported option structure: %s", structure)
                            return None

                        if not buy_instr or not sell_instr:
                            log.info("Option instruments not found for strikes %s/%s; aborting structure", buy_strike, sell_strike)
                            return None

                        # fetch latest quotes if available
                        buy_tick = get_latest_tick_for_instrument(session, buy_instr.instrument_key)
                        sell_tick = get_latest_tick_for_instrument(session, sell_instr.instrument_key)
                        buy_price = float(buy_tick.ltp) if buy_tick else float(plan_payload.get("assumed_price", 20.0))
                        sell_price = float(sell_tick.ltp) if sell_tick else float(plan_payload.get("assumed_price", 10.0))
                        lots = int(plan_payload.get("lots", 1))
                        leg_buy = PaperLeg(leg_id=str(_uuid.uuid4()), instrument_key=buy_instr.instrument_key, side="BUY", quantity=lots * (buy_instr.lot_size or 1), entry_price=buy_price)
                        leg_sell = PaperLeg(leg_id=str(_uuid.uuid4()), instrument_key=sell_instr.instrument_key, side="SELL", quantity=lots * (sell_instr.lot_size or 1), entry_price=sell_price)

                        # risk checks (basic): spread width, liquidity, capital
                        spread = abs(float(sell_price) - float(buy_price))
                        if spread > float(plan_payload.get("max_spread", 500)):
                            log.info("Spread too wide: %.2f > %.2f; rejecting", spread, float(plan_payload.get("max_spread", 500)))
                            return None

                        if self.starting_cash < float(plan_payload.get("min_capital", 500000)):
                            log.info("Insufficient capital: %.2f < %.2f", self.starting_cash, float(plan_payload.get("min_capital", 500000)))
                            return None

                        # submit multi-leg paper order
                        trade_id = f"{sig.action}-{int(datetime.now(timezone.utc).timestamp())}-{_uuid.uuid4().hex[:6]}"
                        morder = self.paper_engine.submit_multi_leg(strategy="NIFTY_HEDGED_V1", trade_id=trade_id, legs=[leg_buy, leg_sell])

                        # persist both leg orders and positions
                        try:
                            with SessionLocal() as sess2:
                                storage.create_order_record(sess2, client_order_id=f"{trade_id}-{leg_buy.leg_id}", trading_mode=self.paper_engine.trading_mode, instrument_key=leg_buy.instrument_key, side=leg_buy.side, quantity=leg_buy.quantity, order_type="LIMIT", requested_price=leg_buy.entry_price, metadata={"trade_id": trade_id, "leg_id": leg_buy.leg_id, "strategy": "NIFTY_HEDGED_V1"})
                                storage.create_order_record(sess2, client_order_id=f"{trade_id}-{leg_sell.leg_id}", trading_mode=self.paper_engine.trading_mode, instrument_key=leg_sell.instrument_key, side=leg_sell.side, quantity=leg_sell.quantity, order_type="LIMIT", requested_price=leg_sell.entry_price, metadata={"trade_id": trade_id, "leg_id": leg_sell.leg_id, "strategy": "NIFTY_HEDGED_V1"})
                                storage.upsert_position_record(sess2, trading_mode=self.paper_engine.trading_mode, instrument_key=leg_buy.instrument_key, quantity=self.ledger.positions.get(leg_buy.instrument_key).quantity if self.ledger.positions.get(leg_buy.instrument_key) else leg_buy.quantity, average_price=self.ledger.positions.get(leg_buy.instrument_key).average_price if self.ledger.positions.get(leg_buy.instrument_key) else leg_buy.entry_price)
                                storage.upsert_position_record(sess2, trading_mode=self.paper_engine.trading_mode, instrument_key=leg_sell.instrument_key, quantity=self.ledger.positions.get(leg_sell.instrument_key).quantity if self.ledger.positions.get(leg_sell.instrument_key) else leg_sell.quantity, average_price=self.ledger.positions.get(leg_sell.instrument_key).average_price if self.ledger.positions.get(leg_sell.instrument_key) else leg_sell.entry_price)
                        except Exception:
                            log.exception("Failed to persist multi-leg order records")

                        log.info("Multi-leg spread executed: trade=%s net_premium=%.2f", trade_id, morder.net_premium())
                        return None
                except Exception as exc:
                    log.exception("Error building/executing option structure: %s", exc)
                    return None

            # Otherwise fall back to single-leg equity/index handling via pipeline
            # Map to pipeline inputs (heuristic values)
            signal_score = float(getattr(sig, "score", 0.0))
            regime_score = 0.6 if snapshot["India VIX"] < 20 else 0.4
            volatility_score = max(0.0, 1.0 - (snapshot["India VIX"] / 100.0))
            cross_asset_score = 0.5
            liquidity_score = 0.8
            risk_reward_score = 0.6

            proposed_risk = 0.005  # 0.5% risk per trade by default
            # Current portfolio risk approximated as absolute net P&L over starting cash
            current_portfolio_risk = abs(self.ledger.net_pnl()) / max(1.0, self.starting_cash)
            daily_loss = -0.01
            weekly_loss = -0.01
            drawdown = 0.02
            correlated_exposure = 0.0

            entry_price = float(tick.ltp)
            # default stop and target
            stop_loss = max(1.0, entry_price - 40.0)
            target = entry_price + 200.0

            decision = self.pipeline.evaluate(
                instrument_key=tick.instrument_key,
                signal_score=signal_score,
                regime_score=regime_score,
                volatility_score=volatility_score,
                cross_asset_score=cross_asset_score,
                liquidity_score=liquidity_score,
                risk_reward_score=risk_reward_score,
                proposed_risk=proposed_risk,
                current_portfolio_risk=current_portfolio_risk,
                daily_loss=daily_loss,
                weekly_loss=weekly_loss,
                drawdown=drawdown,
                correlated_exposure=correlated_exposure,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
            )

            if decision.order is None:
                log.info("No order placed: %s", decision.reason)
                return None

            # Record order fill to ledger
            order = decision.order
            # The PaperOrder contains filled_quantity and average_fill_price
            filled_qty = order.filled_quantity
            fill_price = order.average_fill_price if order.average_fill_price is not None else order.entry_price
            # Normalize action to BUY/SELL for ledger
            raw_side = (order.action or "").upper()
            if "BUY" in raw_side:
                side = "BUY"
            elif "SELL" in raw_side:
                side = "SELL"
            else:
                raise RuntimeError(f"Unsupported order action for ledger: {order.action}")
            # update ledger
            self.ledger.apply_fill(instrument_key=order.instrument_key, quantity=filled_qty, price=fill_price, side=side)
            log.info("Order executed and ledger updated: %s %d @ %.2f", order.instrument_key, filled_qty, fill_price)

            # Persist order and position if DB available
            try:
                from app.database.session import SessionLocal
                import uuid as _uuid
                client_order_id = f"{order.strategy}-{int(datetime.now(timezone.utc).timestamp())}-{_uuid.uuid4().hex[:8]}"
                try:
                    with SessionLocal() as session:
                        orec = storage.create_order_record(session, client_order_id=client_order_id, trading_mode=self.paper_engine.trading_mode, instrument_key=order.instrument_key, side=order.action, quantity=order.quantity, order_type="LIMIT", requested_price=order.entry_price, metadata={"strategy": order.strategy})
                        storage.update_order_fill(session, client_order_id=client_order_id, filled_price=fill_price, filled_quantity=filled_qty)
                        # upsert position
                        pos = self.ledger.positions.get(order.instrument_key)
                        if pos:
                            storage.upsert_position_record(session, trading_mode=self.paper_engine.trading_mode, instrument_key=pos.instrument_key, quantity=pos.quantity, average_price=pos.average_price)
                        # store portfolio snapshot
                        storage.store_portfolio_snapshot(session, trading_mode=self.paper_engine.trading_mode, equity=self.ledger.portfolio_value(), cash=self.ledger.cash, used_margin=0, realized_pnl=0, unrealized_pnl=self.ledger.net_pnl(), details={})
                except Exception:
                    # swallow DB errors to not interrupt live processing
                    pass
            except Exception:
                pass

            # Hedge calculation: compute hedge to neutralize delta exposure (assume 1 delta per unit for index)
            # exposure_delta positive means net long exposure
            exposure_delta = sum(p.quantity for p in self.ledger.positions.values())
            # Hedge instrument per-unit delta assumed to be 1 (future or option equivalent)
            try:
                hedge_qty = compute_hedge_quantity(exposure_delta=float(exposure_delta), hedge_delta=1.0, lot_size=1)
            except Exception:
                hedge_qty = 0

            if hedge_qty != 0:
                # Create a simulated hedge order using paper engine
                hedge_instr = tick.instrument_key
                hedge_decision = PaperOrder(
                    strategy=order.strategy,
                    action="SELL" if hedge_qty < 0 else "BUY",
                    instrument_key=hedge_instr,
                    quantity=abs(hedge_qty),
                    entry_price=fill_price,
                    stop_loss=fill_price,
                    target=fill_price,
                )
                # simulate immediate fill
                hedge_decision.mark_filled()
                self.paper_engine.orders.append(hedge_decision)
                self.ledger.apply_fill(instrument_key=hedge_decision.instrument_key, quantity=hedge_decision.filled_quantity, price=hedge_decision.average_fill_price, side=hedge_decision.action)
                log.info("Hedge placed: %s %d", hedge_decision.instrument_key, hedge_decision.filled_quantity)

            return order
        except Exception as exc:
            log.exception("Unhandled error processing tick: %s", exc)
            return None


import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.broker.upstox_feed import MarketTick
from app.execution.paper import PaperExecutionEngine, PaperOrder, PaperLeg
from app.engine.hedge import compute_hedge_quantity
from app.engine.pipeline import TradePipeline
from app.portfolio.ledger import PositionLedger
from app.strategies.nifty import NiftyStrategy

log = logging.getLogger(__name__)


class TradingEngine:
    """Orchestrates ticks -> strategy -> hedge -> risk -> paper execution -> ledger updates.

    Designed to be simple and deterministic for paper-trading and unit tests.
    """

    def __init__(self, *, strategy: Optional[NiftyStrategy] = None, pipeline: Optional[TradePipeline] = None, paper_engine: Optional[PaperExecutionEngine] = None, ledger: Optional[PositionLedger] = None, starting_cash: float = 500000.0):
        self.strategy = strategy or NiftyStrategy()
        self.paper_engine = paper_engine or PaperExecutionEngine(trading_mode="PAPER")
        self.pipeline = pipeline or TradePipeline(paper_engine=self.paper_engine)
        self.ledger = ledger or PositionLedger(starting_cash=starting_cash)
        self.starting_cash = starting_cash
        # Simple stateful snapshot of last market tick per instrument
        self.last_ticks: dict[str, MarketTick] = {}

    def handle_tick(self, tick: MarketTick) -> Optional[PaperOrder]:
        """Process a single MarketTick and possibly execute a paper trade.

        Returns the executed PaperOrder if one was placed, otherwise None.
        """
        # store last tick
        self.last_ticks[tick.instrument_key] = tick
        try:
            # Build a simple market snapshot expected by the Nifty strategy
            snapshot = {
                "NIFTY": float(tick.ltp),
                "India VIX": float(15.0),  # placeholder; real VIX should come from feed
            }
            # Generate strategy signal
            sig = self.strategy.generate_signal(snapshot)
            log.info("Strategy signal: %s score=%.3f reasons=%s", sig.action, sig.score, sig.reasons)

            # Persist signal if DB available
            try:
                from app.database.session import SessionLocal
                from app.data import storage
                import uuid
                with SessionLocal() as session:
                    try:
                        storage.store_signal(session, strategy="NIFTY_HEDGED_V1", instrument_key=tick.instrument_key, action=sig.action, score=float(sig.score), explanation=str(sig.reasons), payload={"reasons": sig.reasons})
                    except Exception:
                        session.rollback()
            except Exception:
                # DB not available or error; continue without persistence
                pass

            # Default single-leg pipeline values (used if strategy is simple)
            signal_score = float(getattr(sig, "score", 0.0))
            regime_score = 0.6
            volatility_score = 0.5
            cross_asset_score = 0.5
            liquidity_score = 0.8
            risk_reward_score = 0.6
            proposed_risk = 0.005
            current_portfolio_risk = abs(self.ledger.net_pnl()) / max(1.0, self.starting_cash)
            daily_loss = -0.01
            weekly_loss = -0.01
            drawdown = 0.02
            correlated_exposure = 0.0
            entry_price = float(tick.ltp)
            stop_loss = max(1.0, entry_price - 40.0)
            target = entry_price + 200.0

            # If the strategy provided an option_structure payload, handle multi-leg flow here
            try:
                plan_payload = getattr(sig, "payload", None) or {}
            except Exception:
                plan_payload = {}

            if isinstance(plan_payload, dict) and plan_payload.get("option_structure"):
                # dynamic option resolution and multi-leg execution
                from app.database.session import SessionLocal
                from app.market.instrument_lookup import nearest_expiry_for_underlying, atm_strike_from_spot, candidate_strikes, resolve_option_by_strike, get_latest_tick_for_instrument
                from app.data import storage
                import uuid
                with SessionLocal() as session:
                    underlying_key = plan_payload.get("underlying_key") or tick.instrument_key
                    expiry_dt = nearest_expiry_for_underlying(session, underlying_key)
                    if not expiry_dt:
                        log.info("No expiry found for underlying %s; skipping option structure", underlying_key)
                        return None
                    spot = float(tick.ltp)
                    atm = atm_strike_from_spot(spot, strike_step=plan_payload.get("strike_step", 50))
                    # For now support explicit BULL_CALL_SPREAD and BEAR_PUT_SPREAD
                    structure = plan_payload.get("structure")
                    if structure == "BULL_CALL_SPREAD":
                        buy_strike = atm
                        sell_strike = Decimal(int(atm) + int(plan_payload.get("width", 200)))
                        buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, "CE")
                        sell_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, sell_strike, "CE")
                    elif structure == "BEAR_PUT_SPREAD":
                        sell_strike = atm
                        buy_strike = Decimal(int(atm) - int(plan_payload.get("width", 200)))
                        buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, "PE")
                        sell_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, sell_strike, "PE")
                    else:
                        log.info("Unsupported option structure: %s", structure)
                        return None

                    if not buy_instr or not sell_instr:
                        log.info("Option instruments not found for strikes %s/%s; aborting structure", buy_strike, sell_strike)
                        return None

                    # fetch latest quotes if available
                    buy_tick = get_latest_tick_for_instrument(session, buy_instr.instrument_key)
                    sell_tick = get_latest_tick_for_instrument(session, sell_instr.instrument_key)
                    buy_price = float(buy_tick.ltp) if buy_tick else float(plan_payload.get("assumed_price", 20.0))
                    sell_price = float(sell_tick.ltp) if sell_tick else float(plan_payload.get("assumed_price", 10.0))
                    lots = int(plan_payload.get("lots", 1))
                    leg_buy = PaperLeg(leg_id=str(uuid.uuid4()), instrument_key=buy_instr.instrument_key, side="BUY", quantity=lots * (buy_instr.lot_size or 1), entry_price=buy_price)
                    leg_sell = PaperLeg(leg_id=str(uuid.uuid4()), instrument_key=sell_instr.instrument_key, side="SELL", quantity=lots * (sell_instr.lot_size or 1), entry_price=sell_price)

                    # risk checks (basic): spread width, liquidity, capital
                    spread = abs(float(sell_price) - float(buy_price))
                    if spread > float(plan_payload.get("max_spread", 500)):
                        log.info("Spread too wide: %.2f > %.2f; rejecting", spread, float(plan_payload.get("max_spread", 500)))
                        return None

                    # capital check: simple ensure starting cash >= 500000
                    if self.starting_cash < float(plan_payload.get("min_capital", 500000)):
                        log.info("Insufficient capital: %.2f < %.2f", self.starting_cash, float(plan_payload.get("min_capital", 500000)))
                        return None

                    # submit multi-leg paper order
                    trade_id = f"{sig.action}-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:6]}"
                    morder = self.paper_engine.submit_multi_leg(strategy="NIFTY_HEDGED_V1", trade_id=trade_id, legs=[leg_buy, leg_sell])

                    # persist both leg orders
                    try:
                        with SessionLocal() as sess2:
                            storage.create_order_record(sess2, client_order_id=f"{trade_id}-{leg_buy.leg_id}", trading_mode=self.paper_engine.trading_mode, instrument_key=leg_buy.instrument_key, side=leg_buy.side, quantity=leg_buy.quantity, order_type="LIMIT", requested_price=leg_buy.entry_price, metadata={"trade_id": trade_id, "leg_id": leg_buy.leg_id, "strategy": "NIFTY_HEDGED_V1"})
                            storage.create_order_record(sess2, client_order_id=f"{trade_id}-{leg_sell.leg_id}", trading_mode=self.paper_engine.trading_mode, instrument_key=leg_sell.instrument_key, side=leg_sell.side, quantity=leg_sell.quantity, order_type="LIMIT", requested_price=leg_sell.entry_price, metadata={"trade_id": trade_id, "leg_id": leg_sell.leg_id, "strategy": "NIFTY_HEDGED_V1"})
                            storage.upsert_position_record(sess2, trading_mode=self.paper_engine.trading_mode, instrument_key=leg_buy.instrument_key, quantity=self.ledger.positions.get(leg_buy.instrument_key).quantity if self.ledger.positions.get(leg_buy.instrument_key) else leg_buy.quantity, average_price=self.ledger.positions.get(leg_buy.instrument_key).average_price if self.ledger.positions.get(leg_buy.instrument_key) else leg_buy.entry_price)
                            storage.upsert_position_record(sess2, trading_mode=self.paper_engine.trading_mode, instrument_key=leg_sell.instrument_key, quantity=self.ledger.positions.get(leg_sell.instrument_key).quantity if self.ledger.positions.get(leg_sell.instrument_key) else leg_sell.quantity, average_price=self.ledger.positions.get(leg_sell.instrument_key).average_price if self.ledger.positions.get(leg_sell.instrument_key) else leg_sell.entry_price)
                    except Exception:
                        log.exception("Failed to persist multi-leg order records")

                    log.info("Multi-leg spread executed: trade=%s net_premium=%.2f", trade_id, morder.net_premium())
                    return None

            # Otherwise fall back to single-leg equity/index handling via pipeline
            from app.engine.pipeline import TradePipeline
            signal_score = float(signal_score)
            decision = self.pipeline.evaluate(
                instrument_key=tick.instrument_key,
                signal_score=signal_score,
                regime_score=regime_score,
                volatility_score=volatility_score,
                cross_asset_score=cross_asset_score,
                liquidity_score=liquidity_score,
                risk_reward_score=risk_reward_score,
                proposed_risk=proposed_risk,
                current_portfolio_risk=current_portfolio_risk,
                daily_loss=daily_loss,
                weekly_loss=weekly_loss,
                drawdown=drawdown,
                correlated_exposure=correlated_exposure,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
            )

            if decision.order is None:
                log.info("No order placed: %s", decision.reason)
                return None

            # Record order fill to ledger
            order = decision.order
            # The PaperOrder contains filled_quantity and average_fill_price
            filled_qty = order.filled_quantity
            fill_price = order.average_fill_price if order.average_fill_price is not None else order.entry_price
            # Normalize action to BUY/SELL for ledger
            raw_side = (order.action or "").upper()
            if "BUY" in raw_side:
                side = "BUY"
            elif "SELL" in raw_side:
                side = "SELL"
            else:
                raise RuntimeError(f"Unsupported order action for ledger: {order.action}")
            # update ledger
            self.ledger.apply_fill(instrument_key=order.instrument_key, quantity=filled_qty, price=fill_price, side=side)
            log.info("Order executed and ledger updated: %s %d @ %.2f", order.instrument_key, filled_qty, fill_price)

            # Persist order and position if DB available
            try:
                from app.database.session import SessionLocal
                from app.data import storage
                import uuid
                client_order_id = f"{order.strategy}-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:8]}"
                try:
                    with SessionLocal() as session:
                        orec = storage.create_order_record(session, client_order_id=client_order_id, trading_mode=self.paper_engine.trading_mode, instrument_key=order.instrument_key, side=order.action, quantity=order.quantity, order_type="LIMIT", requested_price=order.entry_price, metadata={"strategy": order.strategy})
                        storage.update_order_fill(session, client_order_id=client_order_id, filled_price=fill_price, filled_quantity=filled_qty)
                        # upsert position
                        pos = self.ledger.positions.get(order.instrument_key)
                        if pos:
                            storage.upsert_position_record(session, trading_mode=self.paper_engine.trading_mode, instrument_key=pos.instrument_key, quantity=pos.quantity, average_price=pos.average_price)
                        # store portfolio snapshot
                        storage.store_portfolio_snapshot(session, trading_mode=self.paper_engine.trading_mode, equity=self.ledger.portfolio_value(), cash=self.ledger.cash, used_margin=0, realized_pnl=0, unrealized_pnl=self.ledger.net_pnl(), details={})
                except Exception:
                    # swallow DB errors to not interrupt live processing
                    pass
            except Exception:
                pass

            # Hedge calculation: compute hedge to neutralize delta exposure (assume 1 delta per unit for index)
            # exposure_delta positive means net long exposure
            exposure_delta = sum(p.quantity for p in self.ledger.positions.values())
            # Hedge instrument per-unit delta assumed to be 1 (future or option equivalent)
            try:
                hedge_qty = compute_hedge_quantity(exposure_delta=float(exposure_delta), hedge_delta=1.0, lot_size=1)
            except Exception:
                hedge_qty = 0

            if hedge_qty != 0:
                # Create a simulated hedge order using paper engine
                hedge_instr = tick.instrument_key
                hedge_decision = PaperOrder(
                    strategy=order.strategy,
                    action="SELL" if hedge_qty < 0 else "BUY",
                    instrument_key=hedge_instr,
                    quantity=abs(hedge_qty),
                    entry_price=fill_price,
                    stop_loss=fill_price,
                    target=fill_price,
                )
                # simulate immediate fill
                hedge_decision.mark_filled()
                self.paper_engine.orders.append(hedge_decision)
                self.ledger.apply_fill(instrument_key=hedge_decision.instrument_key, quantity=hedge_decision.filled_quantity, price=hedge_decision.average_fill_price, side=hedge_decision.action)
                log.info("Hedge placed: %s %d", hedge_decision.instrument_key, hedge_decision.filled_quantity)

            return order
        except Exception as exc:
            log.exception("Unhandled error processing tick: %s", exc)
            return None
            signal_score = float(sig.score)
            regime_score = 0.6 if snapshot["India VIX"] < 20 else 0.4
            volatility_score = max(0.0, 1.0 - (snapshot["India VIX"] / 100.0))
            cross_asset_score = 0.5
            liquidity_score = 0.8
            risk_reward_score = 0.6

            proposed_risk = 0.005  # 0.5% risk per trade by default
            # Current portfolio risk approximated as absolute net P&L over starting cash
            current_portfolio_risk = abs(self.ledger.net_pnl()) / max(1.0, self.starting_cash)
            daily_loss = -0.01
            weekly_loss = -0.01
            drawdown = 0.02
            correlated_exposure = 0.0

            entry_price = float(tick.ltp)
            # default stop and target
            stop_loss = max(1.0, entry_price - 40.0)
            target = entry_price + 200.0

            decision = self.pipeline.evaluate(
                instrument_key=tick.instrument_key,
                signal_score=signal_score,
                regime_score=regime_score,
                volatility_score=volatility_score,
                cross_asset_score=cross_asset_score,
                liquidity_score=liquidity_score,
                risk_reward_score=risk_reward_score,
                proposed_risk=proposed_risk,
                current_portfolio_risk=current_portfolio_risk,
                daily_loss=daily_loss,
                weekly_loss=weekly_loss,
                drawdown=drawdown,
                correlated_exposure=correlated_exposure,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
            )

            if decision.order is None:
                log.info("No order placed: %s", decision.reason)
                return None

            # Record order fill to ledger
            order = decision.order
            # The PaperOrder contains filled_quantity and average_fill_price
            filled_qty = order.filled_quantity
            fill_price = order.average_fill_price if order.average_fill_price is not None else order.entry_price
            # Normalize action to BUY/SELL for ledger
            raw_side = (order.action or "").upper()
            if "BUY" in raw_side:
                side = "BUY"
            elif "SELL" in raw_side:
                side = "SELL"
            else:
                raise RuntimeError(f"Unsupported order action for ledger: {order.action}")
            # update ledger
            self.ledger.apply_fill(instrument_key=order.instrument_key, quantity=filled_qty, price=fill_price, side=side)
            log.info("Order executed and ledger updated: %s %d @ %.2f", order.instrument_key, filled_qty, fill_price)

            # Persist order and position if DB available
            try:
                from app.database.session import SessionLocal
                from app.data import storage
                import uuid
                client_order_id = f"{order.strategy}-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:8]}"
                try:
                    with SessionLocal() as session:
                        orec = storage.create_order_record(session, client_order_id=client_order_id, trading_mode=self.paper_engine.trading_mode, instrument_key=order.instrument_key, side=order.action, quantity=order.quantity, order_type="LIMIT", requested_price=order.entry_price, metadata={"strategy": order.strategy})
                        storage.update_order_fill(session, client_order_id=client_order_id, filled_price=fill_price, filled_quantity=filled_qty)
                        # upsert position
                        pos = self.ledger.positions.get(order.instrument_key)
                        if pos:
                            storage.upsert_position_record(session, trading_mode=self.paper_engine.trading_mode, instrument_key=pos.instrument_key, quantity=pos.quantity, average_price=pos.average_price)
                        # store portfolio snapshot
                        storage.store_portfolio_snapshot(session, trading_mode=self.paper_engine.trading_mode, equity=self.ledger.portfolio_value(), cash=self.ledger.cash, used_margin=0, realized_pnl=0, unrealized_pnl=self.ledger.net_pnl(), details={})
                except Exception:
                    # swallow DB errors to not interrupt live processing
                    pass
            except Exception:
                pass

            # Hedge calculation: compute hedge to neutralize delta exposure (assume 1 delta per unit for index)
            # exposure_delta positive means net long exposure
            exposure_delta = sum(p.quantity for p in self.ledger.positions.values())
            # Hedge instrument per-unit delta assumed to be 1 (future or option equivalent)
            try:
                hedge_qty = compute_hedge_quantity(exposure_delta=float(exposure_delta), hedge_delta=1.0, lot_size=1)
            except Exception:
                hedge_qty = 0

            if hedge_qty != 0:
                # Create a simulated hedge order using paper engine
                hedge_instr = tick.instrument_key
                hedge_decision = PaperOrder(
                    strategy=order.strategy,
                    action="SELL" if hedge_qty < 0 else "BUY",
                    instrument_key=hedge_instr,
                    quantity=abs(hedge_qty),
                    entry_price=fill_price,
                    stop_loss=fill_price,
                    target=fill_price,
                )
                # simulate immediate fill
                hedge_decision.mark_filled()
                self.paper_engine.orders.append(hedge_decision)
                self.ledger.apply_fill(instrument_key=hedge_decision.instrument_key, quantity=hedge_decision.filled_quantity, price=hedge_decision.average_fill_price, side=hedge_decision.action)
                log.info("Hedge placed: %s %d", hedge_decision.instrument_key, hedge_decision.filled_quantity)

            return order
                hedge_decision = PaperOrder(
                    strategy=order.strategy,
                    action="SELL" if hedge_qty < 0 else "BUY",
                    instrument_key=hedge_instr,
                    quantity=abs(hedge_qty),
                    entry_price=fill_price,
                    stop_loss=fill_price,
                    target=fill_price,
                )
                # simulate immediate fill
                hedge_decision.mark_filled()
                self.paper_engine.orders.append(hedge_decision)
                self.ledger.apply_fill(instrument_key=hedge_decision.instrument_key, quantity=hedge_decision.filled_quantity, price=hedge_decision.average_fill_price, side=hedge_decision.action)
                log.info("Hedge placed: %s %d", hedge_decision.instrument_key, hedge_decision.filled_quantity)

            return order
        except Exception as exc:
            log.exception("Unhandled error processing tick: %s", exc)
            return None

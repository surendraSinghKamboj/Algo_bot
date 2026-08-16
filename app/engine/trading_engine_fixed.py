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
        # store last tick
        self.last_ticks[tick.instrument_key] = tick
        try:
            snapshot = {"NIFTY": float(tick.ltp), "India VIX": float(15.0)}
            sig = self.strategy.generate_signal(snapshot)
            log.info("Strategy signal: %s score=%s", sig.action, getattr(sig, 'score', None))

            # persist signal if possible
            try:
                from app.database.session import SessionLocal
                with SessionLocal() as s:
                    try:
                        storage.store_signal(s, strategy="NIFTY_HEDGED_V1", instrument_key=tick.instrument_key, action=sig.action, score=float(getattr(sig,'score',0.0)), explanation=str(getattr(sig,'reasons','')), payload=getattr(sig,'payload',{}) or {})
                    except Exception:
                        s.rollback()
            except Exception:
                pass

            plan_payload = getattr(sig, 'payload', {}) or {}
            if isinstance(plan_payload, dict) and plan_payload.get('option_structure'):
                # dynamic option resolution
                from app.database.session import SessionLocal
                import uuid as _uuid
                with SessionLocal() as s:
                    underlying_key = plan_payload.get('underlying_key') or tick.instrument_key
                    expiry_dt = nearest_expiry_for_underlying(s, underlying_key)
                    if not expiry_dt:
                        log.info('no expiry found; aborting')
                        return None
                    spot = float(tick.ltp)
                    atm = atm_strike_from_spot(spot, strike_step=plan_payload.get('strike_step',50))
                    structure = plan_payload.get('structure')
                    if structure == 'BULL_CALL_SPREAD':
                        buy_strike = atm
                        sell_strike = Decimal(int(atm) + int(plan_payload.get('width',200)))
                        buy_instr = resolve_option_by_strike(s, underlying_key, expiry_dt, buy_strike, 'CE')
                        sell_instr = resolve_option_by_strike(s, underlying_key, expiry_dt, sell_strike, 'CE')
                    elif structure == 'BEAR_PUT_SPREAD':
                        sell_strike = atm
                        buy_strike = Decimal(int(atm) - int(plan_payload.get('width',200)))
                        buy_instr = resolve_option_by_strike(s, underlying_key, expiry_dt, buy_strike, 'PE')
                        sell_instr = resolve_option_by_strike(s, underlying_key, expiry_dt, sell_strike, 'PE')
                    else:
                        log.info('unsupported structure: %s', structure)
                        return None

                    if not buy_instr or not sell_instr:
                        log.info('instr not found for strikes %s %s', buy_strike, sell_strike)
                        return None

                    buy_tick = get_latest_tick_for_instrument(s, buy_instr.instrument_key)
                    sell_tick = get_latest_tick_for_instrument(s, sell_instr.instrument_key)
                    buy_price = float(buy_tick.ltp) if buy_tick else float(plan_payload.get('assumed_price',20.0))
                    sell_price = float(sell_tick.ltp) if sell_tick else float(plan_payload.get('assumed_price',10.0))
                    lots = int(plan_payload.get('lots',1))
                    leg_buy = PaperLeg(leg_id=str(_uuid.uuid4()), instrument_key=buy_instr.instrument_key, side='BUY', quantity=lots * (buy_instr.lot_size or 1), entry_price=buy_price)
                    leg_sell = PaperLeg(leg_id=str(_uuid.uuid4()), instrument_key=sell_instr.instrument_key, side='SELL', quantity=lots * (sell_instr.lot_size or 1), entry_price=sell_price)

                    spread = abs(float(sell_price) - float(buy_price))
                    if spread > float(plan_payload.get('max_spread',500)):
                        log.info('spread too wide; rejecting')
                        return None
                    if self.starting_cash < float(plan_payload.get('min_capital',500000)):
                        log.info('insufficient capital; rejecting')
                        return None

                    trade_id = f"{sig.action}-{int(datetime.now(timezone.utc).timestamp())}-{_uuid.uuid4().hex[:6]}"
                    morder = self.paper_engine.submit_multi_leg(strategy='NIFTY_HEDGED_V1', trade_id=trade_id, legs=[leg_buy, leg_sell])

                    # persist legs
                    try:
                        with SessionLocal() as sess:
                            storage.create_order_record(sess, client_order_id=f"{trade_id}-{leg_buy.leg_id}", trading_mode=self.paper_engine.trading_mode, instrument_key=leg_buy.instrument_key, side=leg_buy.side, quantity=leg_buy.quantity, order_type='LIMIT', requested_price=leg_buy.entry_price, metadata={'trade_id': trade_id, 'leg_id': leg_buy.leg_id, 'strategy': 'NIFTY_HEDGED_V1'})
                            storage.create_order_record(sess, client_order_id=f"{trade_id}-{leg_sell.leg_id}", trading_mode=self.paper_engine.trading_mode, instrument_key=leg_sell.instrument_key, side=leg_sell.side, quantity=leg_sell.quantity, order_type='LIMIT', requested_price=leg_sell.entry_price, metadata={'trade_id': trade_id, 'leg_id': leg_sell.leg_id, 'strategy': 'NIFTY_HEDGED_V1'})
                            storage.upsert_position_record(sess, trading_mode=self.paper_engine.trading_mode, instrument_key=leg_buy.instrument_key, quantity=self.ledger.positions.get(leg_buy.instrument_key).quantity if self.ledger.positions.get(leg_buy.instrument_key) else leg_buy.quantity, average_price=self.ledger.positions.get(leg_buy.instrument_key).average_price if self.ledger.positions.get(leg_buy.instrument_key) else leg_buy.entry_price)
                            storage.upsert_position_record(sess, trading_mode=self.paper_engine.trading_mode, instrument_key=leg_sell.instrument_key, quantity=self.ledger.positions.get(leg_sell.instrument_key).quantity if self.ledger.positions.get(leg_sell.instrument_key) else leg_sell.quantity, average_price=self.ledger.positions.get(leg_sell.instrument_key).average_price if self.ledger.positions.get(leg_sell.instrument_key) else leg_sell.entry_price)
                    except Exception:
                        log.exception('failed persist multi-leg')

                    log.info('multi-leg done trade=%s net=%.2f', trade_id, morder.net_premium())
                    return None

            # single leg fallback
            signal_score = float(getattr(sig, 'score', 0.0))
            regime_score = 0.6 if snapshot['India VIX'] < 20 else 0.4
            volatility_score = max(0.0, 1.0 - (snapshot['India VIX'] / 100.0))
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
                log.info('no order placed: %s', decision.reason)
                return None

            order = decision.order
            filled_qty = order.filled_quantity
            fill_price = order.average_fill_price if order.average_fill_price is not None else order.entry_price
            raw_side = (order.action or '').upper()
            if 'BUY' in raw_side:
                side = 'BUY'
            elif 'SELL' in raw_side:
                side = 'SELL'
            else:
                raise RuntimeError(f"Unsupported order action for ledger: {order.action}")

            # apply fill
            self.ledger.apply_fill(instrument_key=order.instrument_key, quantity=filled_qty, price=fill_price, side=side)

            # persist order
            try:
                from app.database.session import SessionLocal
                import uuid as _uuid
                client_order_id = f"{order.strategy}-{int(datetime.now(timezone.utc).timestamp())}-{_uuid.uuid4().hex[:8]}"
                with SessionLocal() as session:
                    storage.create_order_record(session, client_order_id=client_order_id, trading_mode=self.paper_engine.trading_mode, instrument_key=order.instrument_key, side=order.action, quantity=order.quantity, order_type='LIMIT', requested_price=order.entry_price, metadata={'strategy': order.strategy})
                    storage.update_order_fill(session, client_order_id=client_order_id, filled_price=fill_price, filled_quantity=filled_qty)
                    pos = self.ledger.positions.get(order.instrument_key)
                    if pos:
                        storage.upsert_position_record(session, trading_mode=self.paper_engine.trading_mode, instrument_key=pos.instrument_key, quantity=pos.quantity, average_price=pos.average_price)
                    storage.store_portfolio_snapshot(session, trading_mode=self.paper_engine.trading_mode, equity=self.ledger.portfolio_value(), cash=self.ledger.cash, used_margin=0, realized_pnl=0, unrealized_pnl=self.ledger.net_pnl(), details={})
            except Exception:
                pass

            # simple hedge
            exposure_delta = sum(p.quantity for p in self.ledger.positions.values())
            try:
                hedge_qty = compute_hedge_quantity(exposure_delta=float(exposure_delta), hedge_delta=1.0, lot_size=1)
            except Exception:
                hedge_qty = 0

            if hedge_qty != 0:
                hedge_instr = tick.instrument_key
                hedge_decision = PaperOrder(strategy=order.strategy, action='SELL' if hedge_qty < 0 else 'BUY', instrument_key=hedge_instr, quantity=abs(hedge_qty), entry_price=fill_price, stop_loss=fill_price, target=fill_price)
                hedge_decision.mark_filled()
                self.paper_engine.orders.append(hedge_decision)
                self.ledger.apply_fill(instrument_key=hedge_decision.instrument_key, quantity=hedge_decision.filled_quantity, price=hedge_decision.average_fill_price, side=hedge_decision.action)

            return order
        except Exception as exc:
            log.exception('unhandled error processing tick: %s', exc)
            return None

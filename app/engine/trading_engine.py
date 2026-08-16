from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.broker.upstox_feed import MarketTick
from app.data import storage
from app.engine.hedge import compute_hedge_quantity
from app.engine.pipeline import TradePipeline
from app.execution.paper import PaperExecutionEngine, PaperLeg, PaperOrder
from app.market.instrument_lookup import atm_strike_from_spot, get_latest_tick_for_instrument, nearest_expiry_for_underlying, resolve_option_by_strike
from app.market.state import MarketState
from app.portfolio.ledger import PositionLedger
from app.strategies.nifty import NiftyStrategy

log = logging.getLogger(__name__)


class TradingEngine:
    """Paper-trading engine that converts ticks into strategy decisions and fills."""

    def __init__(self, *, strategy: Optional[NiftyStrategy] = None, pipeline: Optional[TradePipeline] = None, paper_engine: Optional[PaperExecutionEngine] = None, ledger: Optional[PositionLedger] = None, starting_cash: float = 500000.0, market_state: Optional[MarketState] = None):
        self.strategy = strategy or NiftyStrategy()
        self.ledger = ledger or PositionLedger(starting_cash=starting_cash)
        self.paper_engine = paper_engine or PaperExecutionEngine(trading_mode='PAPER', ledger=self.ledger)
        if self.paper_engine.ledger is None:
            self.paper_engine.ledger = self.ledger
        self.pipeline = pipeline or TradePipeline(paper_engine=self.paper_engine)
        self.starting_cash = float(starting_cash)
        self.market_state = market_state or MarketState()
        self.last_ticks: dict[str, MarketTick] = {}

    def _market_prices_from_snapshot(self, snapshot: dict) -> dict[str, float]:
        prices: dict[str, float] = {}
        for key, value in snapshot.items():
            if key in {'NIFTY', 'BANKNIFTY', 'INDIA_VIX', 'India VIX', 'Gold', 'Silver', 'Crude', 'USDINR'}:
                prices[key] = float(value)
        return prices

    def _risk_metrics(self, snapshot: dict):
        prices = self._market_prices_from_snapshot(snapshot)
        portfolio_value = self.ledger.portfolio_value(mark_prices=prices)
        net_pnl = self.ledger.net_pnl(mark_prices=prices)
        drawdown = max(0.0, (self.starting_cash - portfolio_value) / max(1.0, self.starting_cash))
        current_portfolio_risk = max(0.0, abs(net_pnl) / max(1.0, self.starting_cash))
        daily_loss = min(0.0, net_pnl) / max(1.0, self.starting_cash)
        weekly_loss = daily_loss
        correlated_exposure = 0.0
        if self.ledger.positions:
            correlated_exposure = min(1.0, sum(abs(pos.quantity) for pos in self.ledger.positions.values()) / max(1, len(self.ledger.positions) * 10))
        return {
            'current_portfolio_risk': current_portfolio_risk,
            'daily_loss': float(daily_loss),
            'weekly_loss': float(weekly_loss),
            'drawdown': float(drawdown),
            'correlated_exposure': float(correlated_exposure),
        }

    @staticmethod
    def _normalize_side(action: Optional[str]) -> str:
        label = (action or '').upper()
        if 'BUY' in label or label in {'LONG', 'BULLISH'} or 'BULL' in label:
            return 'BUY'
        if 'SELL' in label or label in {'SHORT', 'BEARISH'} or 'BEAR' in label:
            return 'SELL'
        return 'BUY' if 'LONG' in label else 'SELL'

    @staticmethod
    def _normalize_signal_action(action: Optional[str]) -> str:
        label = (action or '').upper().replace(' ', '_')
        if label in {'BULLISH', 'BUY', 'LONG', 'BULL'}:
            return 'BULLISH'
        if label in {'BEARISH', 'SELL', 'SHORT', 'BEAR'}:
            return 'BEARISH'
        if label in {'HEDGE', 'RISK_OFF', 'PROTECTIVE_PUT'}:
            return 'HEDGE'
        if label in {'EXIT', 'CLOSE'}:
            return 'EXIT'
        if label in {'NO_TRADE', 'NO TRADE'}:
            return 'NO_TRADE'
        return label if label else 'NO_TRADE'

    def handle_tick(self, tick: MarketTick) -> Optional[PaperOrder]:
        self.last_ticks[tick.instrument_key] = tick
        self.market_state.update_tick(tick)
        snapshot = self.market_state.get_snapshot()
        snapshot['history'] = self.market_state.get_history_map()

        sig = self.strategy.generate_signal(snapshot)
        normalized_action = self._normalize_signal_action(getattr(sig, 'action', None))
        sig.action = normalized_action
        log.info('Strategy signal: %s score=%.3f reasons=%s', sig.action, sig.score, getattr(sig, 'reasons', None))

        plan_payload = getattr(sig, 'payload', {}) or {}
        option_structure_requested = bool(isinstance(plan_payload, dict) and plan_payload.get('option_structure'))
        option_structure_failed = False
        option_structure_data_missing = False
        if option_structure_requested:
            underlying_key = plan_payload.get('underlying_key') or tick.instrument_key
            try:
                from app.database.session import SessionLocal
                with SessionLocal() as session:
                    expiry_dt = nearest_expiry_for_underlying(session, underlying_key)
                    if not expiry_dt:
                        log.info('no expiry found; aborting option structure')
                        option_structure_failed = True
                    else:
                        atm = atm_strike_from_spot(float(tick.ltp), strike_step=plan_payload.get('strike_step', 50))
                        structure = plan_payload.get('structure')

                        if structure == 'BULL_CALL_SPREAD':
                            buy_strike = atm
                            sell_strike = Decimal(int(atm) + int(plan_payload.get('width', 200)))
                            buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, 'CE')
                            sell_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, sell_strike, 'CE')
                        elif structure == 'BEAR_PUT_SPREAD':
                            sell_strike = atm
                            buy_strike = Decimal(int(atm) - int(plan_payload.get('width', 200)))
                            buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, 'PE')
                            sell_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, sell_strike, 'PE')
                        elif structure == 'PROTECTIVE_PUT':
                            buy_strike = atm
                            buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, 'PE')
                            sell_instr = None
                        else:
                            option_structure_failed = True

                        if not option_structure_failed and not buy_instr:
                            log.info('No buy instrument found for structure %s', structure)
                            option_structure_failed = True
                        if not option_structure_failed and structure != 'PROTECTIVE_PUT' and not sell_instr:
                            log.info('No sell instrument found for structure %s', structure)
                            option_structure_failed = True

                        if not option_structure_failed:
                            buy_tick = get_latest_tick_for_instrument(session, buy_instr.instrument_key)
                            if buy_tick is None:
                                log.info('Missing quote for %s; NO TRADE', buy_instr.instrument_key)
                                option_structure_failed = True
                            else:
                                buy_price = float(buy_tick.ltp)
                                if structure == 'PROTECTIVE_PUT':
                                    legs = [PaperLeg(leg_id=f'{datetime.now(timezone.utc).timestamp()}-buy', instrument_key=buy_instr.instrument_key, side='BUY', quantity=(buy_instr.lot_size or 1), entry_price=buy_price)]
                                else:
                                    sell_tick = get_latest_tick_for_instrument(session, sell_instr.instrument_key)
                                    if sell_tick is None:
                                        log.info('Missing quote for %s; NO TRADE', sell_instr.instrument_key)
                                        option_structure_failed = True
                                    else:
                                        sell_price = float(sell_tick.ltp)
                                        legs = [
                                            PaperLeg(leg_id=f'{datetime.now(timezone.utc).timestamp()}-buy', instrument_key=buy_instr.instrument_key, side='BUY', quantity=(buy_instr.lot_size or 1), entry_price=buy_price),
                                            PaperLeg(leg_id=f'{datetime.now(timezone.utc).timestamp()}-sell', instrument_key=sell_instr.instrument_key, side='SELL', quantity=(sell_instr.lot_size or 1), entry_price=sell_price),
                                        ]
                                        net_cost = sum(leg.entry_price * leg.quantity for leg in legs if leg.side == 'BUY') - sum(leg.entry_price * leg.quantity for leg in legs if leg.side == 'SELL')
                                        if abs(net_cost) > float(plan_payload.get('max_spread', 5000)):
                                            log.info('refusing spread with net cost %.2f', net_cost)
                                            option_structure_failed = True
                                        else:
                                            trade_id = f"{sig.action}-{int(datetime.now(timezone.utc).timestamp())}-{datetime.now(timezone.utc).microsecond}"
                                            self.paper_engine.submit_multi_leg(strategy='NIFTY_HEDGED_V1', trade_id=trade_id, legs=legs)
                                            for leg in legs:
                                                self.ledger.apply_fill(instrument_key=leg.instrument_key, quantity=leg.quantity, price=leg.entry_price, side=self._normalize_side(leg.side))
                                            return self.paper_engine.orders[-1] if self.paper_engine.orders else None
                                if not option_structure_failed and structure == 'PROTECTIVE_PUT':
                                    trade_id = f"{sig.action}-{int(datetime.now(timezone.utc).timestamp())}-{datetime.now(timezone.utc).microsecond}"
                                    self.paper_engine.submit_multi_leg(strategy='NIFTY_HEDGED_V1', trade_id=trade_id, legs=legs)
                                    for leg in legs:
                                        self.ledger.apply_fill(instrument_key=leg.instrument_key, quantity=leg.quantity, price=leg.entry_price, side=self._normalize_side(leg.side))
                                    return self.paper_engine.orders[-1] if self.paper_engine.orders else None
            except Exception:
                log.exception('option-structure execution error')
                option_structure_failed = True
                option_structure_data_missing = True

        if option_structure_requested and option_structure_failed and not option_structure_data_missing:
            return None

        if sig.action in {'NO_TRADE', 'NO TRADE'}:
            return None

        risk = self._risk_metrics(snapshot)
        entry_price = float(tick.ltp)
        stop_loss = max(1.0, entry_price - 40.0)
        target = entry_price + 200.0
        decision = self.pipeline.evaluate(
            instrument_key=tick.instrument_key,
            signal_score=float(getattr(sig, 'score', 0.0)),
            regime_score=0.8 if snapshot.get('India VIX', 0.0) < 18 else 0.6,
            volatility_score=max(0.0, 1.0 - (snapshot.get('India VIX', 0.0) / 100.0)),
            cross_asset_score=0.6,
            liquidity_score=0.8,
            risk_reward_score=float(getattr(sig, 'risk_reward', 0.6)),
            proposed_risk=max(0.005, min(0.025, risk['current_portfolio_risk'] + 0.005)),
            current_portfolio_risk=risk['current_portfolio_risk'],
            daily_loss=risk['daily_loss'],
            weekly_loss=risk['weekly_loss'],
            drawdown=risk['drawdown'],
            correlated_exposure=risk['correlated_exposure'],
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
        )
        if decision.order is None:
            log.info('no order placed: %s', decision.reason)
            return None
        order = decision.order
        side = self._normalize_side(getattr(order, 'action', None))
        self.ledger.apply_fill(instrument_key=order.instrument_key, quantity=order.filled_quantity, price=order.average_fill_price or order.entry_price, side=side)
        return order

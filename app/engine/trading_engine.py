from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from app.broker.upstox_feed import MarketTick
from app.data import storage
from app.options.greeks import calculate_option_greeks
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
        availability = snapshot.get('availability', {}) or {}
        prices: dict[str, float] = {}
        for key in ('NIFTY', 'BANKNIFTY', 'INDIA_VIX', 'GOLD', 'SILVER', 'CRUDE', 'USDINR'):
            if availability.get(key, False):
                value = snapshot.get(key, snapshot.get(key.lower(), 0.0))
                if value is not None and float(value) > 0:
                    prices[key] = float(value)
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
            'portfolio_value': float(portfolio_value),
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

    @staticmethod
    def _quote_is_valid(quote, stale_seconds: float = 30.0) -> bool:
        if quote is None:
            return False
        ltp = float(getattr(quote, 'ltp', 0.0) or 0.0)
        if ltp <= 0:
            return False
        observed = getattr(quote, 'observed_at', None) or getattr(quote, 'timestamp', None)
        if observed is None:
            return True
        if getattr(observed, 'tzinfo', None) is None:
            observed = observed.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - observed).total_seconds() > stale_seconds:
            return False
        return True

    @staticmethod
    def _option_trade_metrics(structure: str, *, spot: float, buy_strike: float, sell_strike: float | None, buy_price: float, sell_price: float | None, lot_size: int, expiry_dt: datetime) -> dict:
        buy_greeks = calculate_option_greeks(option_type='CALL' if structure in {'BULL_CALL_SPREAD', 'PROTECTIVE_PUT'} else 'PUT', spot=spot, strike=float(buy_strike), time_to_expiry=max((expiry_dt - datetime.now(timezone.utc)).total_seconds() / 31557600.0, 1e-4), risk_free_rate=0.05, volatility=0.18)
        buy_delta = float(buy_greeks.delta)
        if sell_price is not None and sell_strike is not None:
            sell_type = 'CALL' if structure == 'BULL_CALL_SPREAD' else 'PUT'
            sell_greeks = calculate_option_greeks(option_type=sell_type, spot=spot, strike=float(sell_strike), time_to_expiry=max((expiry_dt - datetime.now(timezone.utc)).total_seconds() / 31557600.0, 1e-4), risk_free_rate=0.05, volatility=0.18)
            sell_delta = float(sell_greeks.delta)
        else:
            sell_delta = 0.0

        if structure == 'BULL_CALL_SPREAD':
            net_debit = (buy_price - sell_price) * lot_size if sell_price is not None else buy_price * lot_size
            max_loss = max(0.0, net_debit)
            max_profit = max(0.0, (float(sell_strike) - float(buy_strike) - max(0.0, buy_price - sell_price)) * lot_size)
            break_even = float(buy_strike) + max(0.0, buy_price - sell_price)
            delta = buy_delta * lot_size - sell_delta * lot_size
            hedge_delta = -0.5
        elif structure == 'BEAR_PUT_SPREAD':
            net_debit = (buy_price - sell_price) * lot_size if sell_price is not None else buy_price * lot_size
            max_loss = max(0.0, net_debit)
            max_profit = max(0.0, (float(buy_strike) - float(sell_strike) - max(0.0, buy_price - sell_price)) * lot_size)
            break_even = float(sell_strike) - max(0.0, buy_price - sell_price)
            delta = -abs(buy_delta * lot_size) + abs(sell_delta * lot_size)
            hedge_delta = 0.5
        elif structure == 'PROTECTIVE_PUT':
            max_loss = max(0.0, (float(buy_strike) - spot + buy_price) * lot_size)
            max_profit = max(0.0, (spot - buy_price) * lot_size)
            break_even = float(buy_strike) - buy_price
            delta = buy_delta * lot_size
            hedge_delta = 0.5
        else:
            max_loss = 0.0
            max_profit = 0.0
            break_even = 0.0
            delta = 0.0
            hedge_delta = 0.0

        hedge_quantity = int(compute_hedge_quantity(exposure_delta=float(delta), hedge_delta=hedge_delta, lot_size=max(1, int(lot_size))) if hedge_delta != 0 else 0)
        residual_delta = float(delta + (hedge_delta * hedge_quantity))
        return {
            'delta': float(delta),
            'gamma': float(buy_greeks.gamma),
            'theta': float(buy_greeks.theta),
            'vega': float(buy_greeks.vega),
            'max_loss': float(max_loss),
            'max_profit': float(max_profit),
            'break_even': float(break_even),
            'entry_debit': float((buy_price * lot_size) - (sell_price * lot_size if sell_price is not None else 0.0)),
            'liquidity': 'good' if (sell_price is None or max(0.0, abs(buy_price - sell_price)) < 0.35) else 'poor',
            'iv': 0.18,
            'spread_slippage': abs(buy_price - (sell_price if sell_price is not None else buy_price)),
            'capital_requirement': float((buy_price * lot_size) + (sell_price * lot_size if sell_price is not None else 0.0)),
            'hedge_delta': float(hedge_delta),
            'hedge_quantity': int(hedge_quantity),
            'residual_delta': float(residual_delta),
            'hedge_cost': float(abs(hedge_quantity) * max(0.0, buy_price if hedge_delta > 0 else (sell_price or buy_price))),
        }

    def _persist_trade_cycle(self, *, signal, order=None, multi_order=None) -> None:
        try:
            from app.config.db import get_database_url
            from app.database.models import Base, OrderRecord, PositionRecord, SignalRecord
            from app.database.session import SessionLocal

            if 'postgres' not in get_database_url().lower():
                return
            with SessionLocal() as session:
                try:
                    Base.metadata.create_all(bind=session.bind)
                except Exception:
                    pass
                if signal is not None:
                    session.add(SignalRecord(
                        strategy='NIFTY_HEDGED_V1',
                        instrument_key=getattr(signal, 'instrument_key', None) or 'NSE_INDEX|Nifty 50',
                        observed_at=datetime.now(timezone.utc),
                        action=str(getattr(signal, 'action', 'NO_TRADE')).upper(),
                        score=float(getattr(signal, 'score', 0.0)),
                        status='ACTIVE',
                        explanation=str(getattr(signal, 'reasons', {})),
                        payload=getattr(signal, 'payload', {}) or {},
                    ))
                if order is not None:
                    session.add(OrderRecord(
                        client_order_id=f"paper-{int(datetime.now(timezone.utc).timestamp()*1000)}",
                        trading_mode='PAPER',
                        instrument_key=order.instrument_key,
                        side='BUY' if 'BUY' in str(order.action).upper() or 'LONG' in str(order.action).upper() else 'SELL',
                        quantity=int(order.filled_quantity or order.quantity),
                        order_type='LIMIT',
                        status='FILLED',
                        requested_price=Decimal(str(order.entry_price)),
                        filled_price=Decimal(str(order.average_fill_price or order.entry_price)),
                        filled_quantity=int(order.filled_quantity or order.quantity),
                        estimated_cost=Decimal(str((order.average_fill_price or order.entry_price) * (order.filled_quantity or order.quantity))),
                        metadata_json={'strategy': order.strategy, 'trade_id': None},
                    ))
                if multi_order is not None:
                    for leg in multi_order.legs:
                        session.add(OrderRecord(
                            client_order_id=f"paper-{int(datetime.now(timezone.utc).timestamp()*1000)}-{leg.leg_id}",
                            trading_mode='PAPER',
                            instrument_key=leg.instrument_key,
                            side=leg.side.upper(),
                            quantity=int(leg.filled_quantity or leg.quantity),
                            order_type='LIMIT',
                            status='FILLED',
                            requested_price=Decimal(str(leg.entry_price)),
                            filled_price=Decimal(str(leg.average_fill_price or leg.entry_price)),
                            filled_quantity=int(leg.filled_quantity or leg.quantity),
                            estimated_cost=Decimal(str((leg.average_fill_price or leg.entry_price) * (leg.filled_quantity or leg.quantity))),
                            metadata_json={'strategy': multi_order.strategy, 'trade_id': multi_order.trade_id, 'leg_id': leg.leg_id},
                        ))
                for instrument_key, position in self.ledger.positions.items():
                    session.add(PositionRecord(
                        trading_mode='PAPER',
                        instrument_key=instrument_key,
                        quantity=int(position.quantity),
                        average_price=Decimal(str(position.average_price or 0.0)),
                        realized_pnl=Decimal(str(0.0)),
                    ))
                session.commit()
        except Exception:
            log.exception('paper trade persistence failed')

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
                        width = int(plan_payload.get('width', 200))
                        lot_size = int(plan_payload.get('lots', 1) or 1)

                        if structure == 'BULL_CALL_SPREAD':
                            buy_strike = atm
                            sell_strike = Decimal(int(atm) + width)
                            buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, 'CE')
                            sell_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, sell_strike, 'CE')
                        elif structure == 'BEAR_PUT_SPREAD':
                            sell_strike = atm
                            buy_strike = Decimal(int(atm) - width)
                            buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, 'PE')
                            sell_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, sell_strike, 'PE')
                        elif structure == 'PROTECTIVE_PUT':
                            buy_strike = atm
                            sell_strike = None
                            buy_instr = resolve_option_by_strike(session, underlying_key, expiry_dt, buy_strike, 'PE')
                            sell_instr = None
                        else:
                            option_structure_failed = True
                            buy_instr = None
                            sell_instr = None

                        if not option_structure_failed and not buy_instr:
                            log.info('No buy instrument found for structure %s', structure)
                            option_structure_failed = True
                        if not option_structure_failed and structure != 'PROTECTIVE_PUT' and not sell_instr:
                            log.info('No sell instrument found for structure %s', structure)
                            option_structure_failed = True

                        if not option_structure_failed:
                            buy_tick = get_latest_tick_for_instrument(session, buy_instr.instrument_key)
                            if not self._quote_is_valid(buy_tick):
                                log.info('Missing or stale quote for %s; NO TRADE', buy_instr.instrument_key)
                                option_structure_failed = True
                            else:
                                buy_price = float(buy_tick.ltp)
                                sell_price = None
                                if structure == 'PROTECTIVE_PUT':
                                    legs = [PaperLeg(leg_id=f'{datetime.now(timezone.utc).timestamp()}-buy', instrument_key=buy_instr.instrument_key, side='BUY', quantity=lot_size, entry_price=buy_price)]
                                else:
                                    sell_tick = get_latest_tick_for_instrument(session, sell_instr.instrument_key)
                                    if not self._quote_is_valid(sell_tick):
                                        log.info('Missing or stale quote for %s; NO TRADE', sell_instr.instrument_key)
                                        option_structure_failed = True
                                    else:
                                        sell_price = float(sell_tick.ltp)
                                        legs = [
                                            PaperLeg(leg_id=f'{datetime.now(timezone.utc).timestamp()}-buy', instrument_key=buy_instr.instrument_key, side='BUY', quantity=lot_size, entry_price=buy_price),
                                            PaperLeg(leg_id=f'{datetime.now(timezone.utc).timestamp()}-sell', instrument_key=sell_instr.instrument_key, side='SELL', quantity=lot_size, entry_price=sell_price),
                                        ]

                                if not option_structure_failed:
                                    metrics = self._option_trade_metrics(
                                        structure,
                                        spot=float(tick.ltp),
                                        buy_strike=float(buy_strike),
                                        sell_strike=float(sell_strike) if sell_strike is not None else None,
                                        buy_price=buy_price,
                                        sell_price=sell_price,
                                        lot_size=lot_size,
                                        expiry_dt=expiry_dt,
                                    )
                                    max_spread = float(plan_payload.get('max_spread', 5000))
                                    if metrics['max_loss'] <= 0 or metrics['max_profit'] <= 0:
                                        log.info('Rejected option structure %s: invalid payoff metrics', structure)
                                        option_structure_failed = True
                                    elif abs(metrics['entry_debit']) > max_spread:
                                        log.info('refusing spread with net cost %.2f', metrics['entry_debit'])
                                        option_structure_failed = True
                                    else:
                                        risk = self._risk_metrics(snapshot)
                                        allowed_risk = 0.02 * self.starting_cash
                                        if metrics['max_loss'] > allowed_risk:
                                            log.info('Rejected option structure due to capital risk %.2f > %.2f', metrics['max_loss'], allowed_risk)
                                            option_structure_failed = True
                                        else:
                                            trade_id = f"{sig.action}-{int(datetime.now(timezone.utc).timestamp())}-{datetime.now(timezone.utc).microsecond}"
                                            multi_order = self.paper_engine.submit_multi_leg(strategy='NIFTY_HEDGED_V1', trade_id=trade_id, legs=legs, strategy_id='NIFTY_HEDGED_V1')
                                            self._persist_trade_cycle(signal=sig, multi_order=multi_order)
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
        self._persist_trade_cycle(signal=sig, order=order)
        return order

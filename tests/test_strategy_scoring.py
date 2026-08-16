from app.options.structures import OptionType, SpreadDefinition, SpreadType
from app.strategies.scoring import ScoreBreakdown, StrategyScorer


def test_strategy_scorer_rejects_weak_setup():
    scorer = StrategyScorer(min_trade_score=0.6)
    score = scorer.score(
        signal_score=0.2,
        regime_score=0.4,
        volatility_score=0.2,
        cross_asset_score=0.3,
        liquidity_score=0.25,
        risk_reward_score=0.1,
    )
    assert score.final_score < 0.6
    assert score.action == "NO TRADE"


def test_strategy_scorer_accepts_strong_setup():
    scorer = StrategyScorer(min_trade_score=0.6)
    score = scorer.score(
        signal_score=0.9,
        regime_score=0.85,
        volatility_score=0.8,
        cross_asset_score=0.75,
        liquidity_score=0.9,
        risk_reward_score=0.88,
    )
    assert score.final_score >= 0.6
    assert score.action in {"BUY", "BUY_HEDGE", "SELL"}


def test_option_spread_candidate_rejects_bad_risk_profile():
    candidate = SpreadDefinition(
        spread_type=SpreadType.BULL_CALL,
        entry_price=40.0,
        max_loss=150.0,
        max_profit=80.0,
        break_even=41.2,
        risk_reward_ratio=0.53,
        delta=0.38,
        gamma=0.02,
        theta=-0.04,
        vega=0.09,
        iv=18.0,
        expected_move=1.2,
        distance_to_expiry=9,
        bid_ask_spread=0.5,
        liquidity="poor",
        margin_requirement=25000.0,
        risk_budget=10000.0,
    )
    assert candidate.is_acceptable() is False


def test_option_spread_candidate_accepts_safe_defined_risk_trade():
    candidate = SpreadDefinition(
        spread_type=SpreadType.BEAR_PUT,
        entry_price=18.0,
        max_loss=120.0,
        max_profit=180.0,
        break_even=16.4,
        risk_reward_ratio=1.5,
        delta=-0.42,
        gamma=0.018,
        theta=-0.03,
        vega=0.08,
        iv=17.0,
        expected_move=1.4,
        distance_to_expiry=18,
        bid_ask_spread=0.15,
        liquidity="good",
        margin_requirement=18000.0,
        risk_budget=20000.0,
    )
    assert candidate.is_acceptable() is True
    assert candidate.max_loss <= candidate.risk_budget

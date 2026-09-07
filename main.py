"""
SilverQuant v8.8 - نسخة موحدة (المحرك + واجهة Kivy) لبناء APK عبر Buildozer
"""

from __future__ import annotations
import os
import sys
import math
import time
import json
import random
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("SilverQuant_v8_8")

# ═════════════════════════════════════════════════════════════════════════════
# 1. الثوابت والهياكل
# ═════════════════════════════════════════════════════════════════════════════

class QuantSignalType(Enum):
    STRONG_BUY  = "STRONG_BUY"
    BUY         = "BUY"
    NEUTRAL     = "NEUTRAL"
    SELL        = "SELL"
    STRONG_SELL = "STRONG_SELL"

class MarketSession(Enum):
    SYDNEY             = "SYDNEY"
    TOKYO              = "TOKYO"
    LONDON             = "LONDON"
    NEW_YORK           = "NEW_YORK"
    LONDON_NY_OVERLAP  = "LONDON_NY_OVERLAP"
    DEAD_ZONE          = "DEAD_ZONE"
    CLOSED             = "CLOSED"

class MarketRegime(Enum):
    TRENDING_BULL         = "TRENDING_BULL"
    TRENDING_BEAR         = "TRENDING_BEAR"
    MEAN_REVERTING_RANGE  = "MEAN_REVERTING_RANGE"
    VOLATILITY_EXPANSION  = "VOLATILITY_EXPANSION"

class StrategySetupType(Enum):
    ORDER_BLOCK_MITIGATION    = "ORDER_BLOCK_MITIGATION"
    FAIR_VALUE_GAP_RETEST     = "FAIR_VALUE_GAP_RETEST"
    LIQUIDITY_SWEEP_REVERSAL  = "LIQUIDITY_SWEEP_REVERSAL"
    EMA_MOMENTUM_PULLBACK     = "EMA_MOMENTUM_PULLBACK"
    HOURLY_OPPORTUNITY_SCALP  = "HOURLY_OPPORTUNITY_SCALP"
    HOURLY_MANDATORY_FALLBACK = "HOURLY_MANDATORY_FALLBACK"

class DataSourceType(Enum):
    LIVE_NETWORK_FEED             = "LIVE_NETWORK_FEED"
    EMPIRICAL_MICROSTRUCTURE_FLOW = "EMPIRICAL_MICROSTRUCTURE_FLOW"

@dataclass
class EngineConfig:
    symbol: str = "XAGUSD"
    account_balance: float = 10000.0
    account_equity: float = 10000.0
    max_portfolio_heat_pct: float = 0.02
    base_trade_risk_pct: float = 0.008
    hourly_micro_risk_pct: float = 0.002
    silver_contract_size: float = 5000.0
    base_spread_points: float = 0.025
    rollover_spread_points: float = 0.080
    max_tolerated_spread: float = 0.045
    max_concurrent_trades: int = 3
    enable_auto_network: bool = True

@dataclass
class TechnicalFeaturesBundle:
    rsi_current: float
    rsi_previous: float
    macd_line: float
    macd_signal: float
    macd_hist: float
    atr: float
    bb_upper: float
    bb_mid: float
    bb_lower: float
    ema20: float

@dataclass
class TradeSignal:
    timestamp: datetime
    symbol: str
    signal_type: QuantSignalType
    strategy: StrategySetupType
    price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    confidence_score: float
    regime: MarketRegime
    session: MarketSession
    is_hourly_fallback: bool = False
    is_breakeven_moved: bool = False
    data_source: DataSourceType = DataSourceType.EMPIRICAL_MICROSTRUCTURE_FLOW
    meta_info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TradeOutcome:
    trade_id: str
    symbol: str
    direction: str
    strategy: StrategySetupType
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    spread_cost: float
    pnl_net: float
    return_pct: float
    exit_reason: str

@dataclass
class BacktestReport:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    hourly_trades_count: int
    hourly_trades_win_rate: float
    total_spread_cost: float

# ═════════════════════════════════════════════════════════════════════════════
# 2. المؤشرات الفنية والرياضية القياسية
# ═════════════════════════════════════════════════════════════════════════════

class SmartFeatureEngine:
    def __init__(self, rsi_period: int = 14, atr_period: int = 14, bb_period: int = 20):
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.bb_period = bb_period

    def compute_rsi(self, closes: List[float]) -> float:
        if len(closes) < self.rsi_period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i - 1]
            gains.append(max(d, 0.0))
            losses.append(abs(min(d, 0.0)))
        avg_gain = sum(gains[:self.rsi_period]) / self.rsi_period
        avg_loss = sum(losses[:self.rsi_period]) / self.rsi_period
        for i in range(self.rsi_period, len(gains)):
            avg_gain = (avg_gain * (self.rsi_period - 1) + gains[i]) / self.rsi_period
            avg_loss = (avg_loss * (self.rsi_period - 1) + losses[i]) / self.rsi_period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def compute_atr(self, highs: List[float], lows: List[float], closes: List[float]) -> float:
        if len(highs) < self.atr_period + 1:
            return 0.15
        trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, len(highs))]
        atr = sum(trs[:self.atr_period]) / self.atr_period
        for i in range(self.atr_period, len(trs)):
            atr = (atr * (self.atr_period - 1) + trs[i]) / self.atr_period
        return max(atr, 0.05)

    def compute_bollinger_bands(self, closes: List[float], std_multiplier: float = 2.0) -> Tuple[float, float, float]:
        if len(closes) < self.bb_period:
            v = closes[-1] if closes else 30.0
            return v + 0.5, v, v - 0.5
        w = closes[-self.bb_period:]
        sma = sum(w) / self.bb_period
        variance = sum((x - sma) ** 2 for x in w) / self.bb_period
        std = math.sqrt(variance)
        return sma + (std * std_multiplier), sma, sma - (std * std_multiplier)

    def compute_ema(self, series: List[float], period: int) -> float:
        if not series:
            return 30.0
        if len(series) < period:
            return sum(series) / len(series)
        mult = 2.0 / (period + 1.0)
        ema = sum(series[:period]) / period
        for val in series[period:]:
            ema = (val - ema) * mult + ema
        return ema

    def compute_macd(self, closes: List[float]) -> Tuple[float, float, float]:
        if len(closes) < 35:
            return 0.0, 0.0, 0.0
        macd_series = []
        for k in range(26, len(closes) + 1):
            sub = closes[:k]
            macd_series.append(self.compute_ema(sub, 12) - self.compute_ema(sub, 26))
        macd_line = macd_series[-1]
        signal_line = self.compute_ema(macd_series, 9)
        return macd_line, signal_line, macd_line - signal_line

    def extract_unified_bundle(self, highs: List[float], lows: List[float], closes: List[float]) -> TechnicalFeaturesBundle:
        rsi_curr = self.compute_rsi(closes)
        rsi_prev = self.compute_rsi(closes[:-1]) if len(closes) > 1 else rsi_curr
        macd_l, macd_s, macd_h = self.compute_macd(closes)
        atr_val = self.compute_atr(highs, lows, closes)
        bb_u, bb_m, bb_l = self.compute_bollinger_bands(closes)
        ema_20 = self.compute_ema(closes, 20)
        return TechnicalFeaturesBundle(
            rsi_current=rsi_curr, rsi_previous=rsi_prev,
            macd_line=macd_l, macd_signal=macd_s, macd_hist=macd_h,
            atr=atr_val, bb_upper=bb_u, bb_mid=bb_m, bb_lower=bb_l, ema20=ema_20
        )

# ═════════════════════════════════════════════════════════════════════════════
# 3. التعلم الآلي البايزي
# ═════════════════════════════════════════════════════════════════════════════

class AdaptiveBayesianRegimeLearner:
    def __init__(self, learning_rate: float = 0.02, l2_reg: float = 0.01):
        self.learning_rate = learning_rate
        self.l2_reg = l2_reg
        self.weights = [0.25, 0.20, 0.15, 0.20, 0.20]
        self.alpha_prior = 6.0
        self.beta_prior = 4.0
        self.wins_count = 0
        self.losses_count = 0

    def extract_feature_vector(self, bundle: TechnicalFeaturesBundle, close: float, flow_imbalance: float) -> List[float]:
        rsi_grad = (bundle.rsi_current - bundle.rsi_previous) / 10.0
        macd_acc = bundle.macd_hist * 10.0
        atr_ratio = (bundle.atr / 0.15) - 1.0
        bb_width = max(bundle.bb_upper - bundle.bb_lower, 0.01)
        bb_pct_b = ((close - bundle.bb_lower) / bb_width) - 0.5
        raw = [rsi_grad, macd_acc, atr_ratio, bb_pct_b, flow_imbalance]
        return [math.tanh(x) for x in raw]

    def predict_win_probability(self, features: List[float], direction: str) -> float:
        sign = 1.0 if direction == "BUY" else -1.0
        z = sum(w * f * sign for w, f in zip(self.weights, features))
        p_logistic = 1.0 / (1.0 + math.exp(-max(min(z, 5.0), -5.0)))
        a = self.alpha_prior + self.wins_count
        b = self.beta_prior + self.losses_count
        p_bayesian = a / (a + b)
        combined = (0.65 * p_logistic) + (0.35 * p_bayesian)
        return round(max(min(combined, 0.88), 0.15), 4)

    def update_model(self, features: List[float], direction: str, is_win: bool):
        sign = 1.0 if direction == "BUY" else -1.0
        target = 1.0 if is_win else 0.0
        if is_win:
            self.wins_count += 1
        else:
            self.losses_count += 1
        z = sum(w * f * sign for w, f in zip(self.weights, features))
        pred = 1.0 / (1.0 + math.exp(-max(min(z, 5.0), -5.0)))
        error = pred - target
        for i in range(len(self.weights)):
            grad = error * features[i] * sign + (self.l2_reg * self.weights[i])
            self.weights[i] -= self.learning_rate * grad

    def detect_regime(self, closes: List[float], atr: float) -> MarketRegime:
        if len(closes) < 20:
            return MarketRegime.MEAN_REVERTING_RANGE
        ret = (closes[-1] - closes[-20]) / closes[-20]
        if atr > 0.28:
            return MarketRegime.VOLATILITY_EXPANSION
        elif ret > 0.012:
            return MarketRegime.TRENDING_BULL
        elif ret < -0.012:
            return MarketRegime.TRENDING_BEAR
        return MarketRegime.MEAN_REVERTING_RANGE

# ═════════════════════════════════════════════════════════════════════════════
# 4. المعنويات وتدفق الأوامر وحماية السبريد
# ═════════════════════════════════════════════════════════════════════════════

class MarketSentimentAndOrderFlowEngine:
    def __init__(self, enable_live_network: bool = True):
        self.enable_live_network = enable_live_network
        self.latest_dxy: Optional[float] = None
        self.dxy_window: List[float] = []
        self.is_connected = False
        self.lock = threading.Lock()
        if self.enable_live_network:
            self._start_fetcher()

    def _start_fetcher(self):
        def loop():
            while True:
                try:
                    self._fetch()
                except Exception:
                    self.is_connected = False
                time.sleep(60)
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _fetch(self):
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1m&range=1d"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                p = data.get('chart', {}).get('result', [{}])[0].get('meta', {}).get('regularMarketPrice')
                if p:
                    with self.lock:
                        self.latest_dxy = float(p)
                        self.dxy_window.append(float(p))
                        if len(self.dxy_window) > 60:
                            self.dxy_window.pop(0)
                        self.is_connected = True

    def get_order_flow_imbalance(self, highs, lows, closes, opens, volumes) -> Tuple[float, DataSourceType]:
        with self.lock:
            if self.is_connected and len(self.dxy_window) >= 5:
                mean = sum(self.dxy_window) / len(self.dxy_window)
                var = sum((x - mean) ** 2 for x in self.dxy_window) / len(self.dxy_window)
                std = math.sqrt(var) if var > 0 else 0.05
                z = (self.latest_dxy - mean) / std
                return -math.tanh(z * 0.5), DataSourceType.LIVE_NETWORK_FEED
        if len(closes) < 5:
            return 0.0, DataSourceType.EMPIRICAL_MICROSTRUCTURE_FLOW
        lookback = min(len(closes), 10)
        buy_flow, sell_flow = 0.0, 0.0
        for i in range(-lookback, 0):
            c, o, h, l = closes[i], opens[i], highs[i], lows[i]
            v = volumes[i] if i < len(volumes) and volumes[i] > 0 else 1000.0
            buy_flow += (max(c - o, 0.0) + ((min(c, o) - l) * 0.7)) * v
            sell_flow += (max(o - c, 0.0) + ((h - max(c, o)) * 0.7)) * v
        total = max(buy_flow + sell_flow, 1.0)
        imbalance = (buy_flow - sell_flow) / total
        return round(max(min(imbalance, 1.0), -1.0), 3), DataSourceType.EMPIRICAL_MICROSTRUCTURE_FLOW

class MarketSessionManager:
    @staticmethod
    def get_current_session(dt: Optional[datetime] = None) -> MarketSession:
        if dt is None:
            dt = datetime.now(timezone.utc)
        h = dt.hour
        if dt.weekday() == 5 or (dt.weekday() == 6 and h < 22):
            return MarketSession.CLOSED
        if 8 <= h < 12:
            return MarketSession.LONDON
        elif 13 <= h < 17:
            return MarketSession.LONDON_NY_OVERLAP
        elif 17 <= h < 21:
            return MarketSession.NEW_YORK
        elif 21 <= h < 23:
            return MarketSession.DEAD_ZONE
        elif 0 <= h < 7:
            return MarketSession.TOKYO
        return MarketSession.SYDNEY

class SilverSpreadAndRolloverGuard:
    def __init__(self, config: EngineConfig):
        self.config = config

    def get_spread(self, dt: Optional[datetime] = None) -> float:
        if dt is None:
            dt = datetime.now(timezone.utc)
        if (dt.hour == 21) or (dt.hour == 22 and dt.minute <= 15):
            return self.config.rollover_spread_points
        sess = MarketSessionManager.get_current_session(dt)
        if sess in [MarketSession.LONDON_NY_OVERLAP, MarketSession.LONDON]:
            return self.config.base_spread_points
        return self.config.base_spread_points * 1.3

    def is_blackout(self, dt: Optional[datetime] = None) -> bool:
        if dt is None:
            dt = datetime.now(timezone.utc)
        return (dt.hour == 21 and dt.minute >= 55) or (dt.hour == 22 and dt.minute <= 15)

# ═════════════════════════════════════════════════════════════════════════════
# 5. محرك الصفقة الساعية الإلزامية
# ═════════════════════════════════════════════════════════════════════════════

class HourlyFallbackExecutor:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.current_tracked_hour: int = -1
        self.trades_in_hour: int = 0

    def notify_trade(self, dt: datetime):
        if dt.hour != self.current_tracked_hour:
            self.current_tracked_hour = dt.hour
            self.trades_in_hour = 1
        else:
            self.trades_in_hour += 1

    def scan_hourly_trade(self, dt, price, bundle, spread, session, regime, learner, flow_imbalance) -> Optional[TradeSignal]:
        if dt.hour != self.current_tracked_hour:
            self.current_tracked_hour = dt.hour
            self.trades_in_hour = 0

        minute = dt.minute
        has_executed = (self.trades_in_hour > 0)

        if minute < 45:
            threshold = 0.60
        elif 45 <= minute < 55:
            threshold = 0.35
        else:
            threshold = 0.0 if not has_executed else 0.50

        if has_executed and minute >= 55:
            return None

        bullish_bias_score = 0
        if price >= bundle.ema20:
            bullish_bias_score += 1
        if bundle.macd_hist >= 0:
            bullish_bias_score += 1
        if flow_imbalance >= 0:
            bullish_bias_score += 1
        if price <= bundle.bb_lower:
            bullish_bias_score += 2
        elif price >= bundle.bb_upper:
            bullish_bias_score -= 2

        direction_buy = (bullish_bias_score >= 2)
        dir_type = QuantSignalType.BUY if direction_buy else QuantSignalType.SELL

        features = learner.extract_feature_vector(bundle, price, flow_imbalance)
        conf = learner.predict_win_probability(features, "BUY" if direction_buy else "SELL")

        if conf < threshold and not (minute >= 55 and not has_executed):
            return None

        is_last_resort = (minute >= 55 and not has_executed)
        strat = StrategySetupType.HOURLY_MANDATORY_FALLBACK if is_last_resort else StrategySetupType.HOURLY_OPPORTUNITY_SCALP

        sl_dist = max(bundle.atr * 0.85, spread * 2.5)
        tp_dist = sl_dist * 1.5
        sl = round(price - sl_dist, 4) if direction_buy else round(price + sl_dist, 4)
        tp = round(price + tp_dist + spread, 4) if direction_buy else round(price - tp_dist - spread, 4)

        risk_pct = self.config.hourly_micro_risk_pct if is_last_resort else self.config.base_trade_risk_pct
        risk_amt = self.config.account_equity * risk_pct
        lot = round(risk_amt / max(sl_dist * self.config.silver_contract_size, 1.0), 2)
        lot = max(min(lot, 1.0), 0.01)

        self.notify_trade(dt)
        return TradeSignal(
            timestamp=dt, symbol=self.config.symbol, signal_type=dir_type, strategy=strat,
            price=price, stop_loss=sl, take_profit=tp, lot_size=lot, confidence_score=conf,
            regime=regime, session=session, is_hourly_fallback=is_last_resort,
            meta_info={"hour": dt.hour, "minute": minute, "is_mandatory": is_last_resort}
        )

# ═════════════════════════════════════════════════════════════════════════════
# 6. مجمع الاستراتيجيات المؤسسية
# ═════════════════════════════════════════════════════════════════════════════

class MultiSetupInstitutionalScanner:
    @staticmethod
    def scan_opportunities(highs, lows, closes, opens, bundle, spread, learner, flow_imbalance, regime, session):
        results = []
        if len(closes) < 35:
            return results
        price = closes[-1]
        features_buy = learner.extract_feature_vector(bundle, price, flow_imbalance)

        is_bull_ob = (closes[-5] < opens[-5]) and (closes[-1] > max(highs[-5:-1]))
        is_bear_ob = (closes[-5] > opens[-5]) and (closes[-1] < min(lows[-5:-1]))
        if is_bull_ob or is_bear_ob:
            dir_type = QuantSignalType.BUY if is_bull_ob else QuantSignalType.SELL
            conf = learner.predict_win_probability(features_buy, "BUY" if is_bull_ob else "SELL")
            if conf >= 0.65:
                sl_dist = max(bundle.atr * 1.2, spread * 3.0)
                sl = round(price - sl_dist, 4) if is_bull_ob else round(price + sl_dist, 4)
                tp = round(price + (sl_dist * 2.0) + spread, 4) if is_bull_ob else round(price - (sl_dist * 2.0) - spread, 4)
                results.append((StrategySetupType.ORDER_BLOCK_MITIGATION, dir_type, price, sl, tp, conf))

        if len(highs) >= 4:
            fvg_bull = (lows[-1] > highs[-3]) and (price <= lows[-1])
            fvg_bear = (highs[-1] < lows[-3]) and (price >= highs[-1])
            if fvg_bull or fvg_bear:
                dir_type = QuantSignalType.BUY if fvg_bull else QuantSignalType.SELL
                conf = learner.predict_win_probability(features_buy, "BUY" if fvg_bull else "SELL")
                if conf >= 0.68:
                    sl_dist = max(bundle.atr * 1.0, spread * 2.5)
                    sl = round(price - sl_dist, 4) if fvg_bull else round(price + sl_dist, 4)
                    tp = round(price + (sl_dist * 1.8) + spread, 4) if fvg_bull else round(price - (sl_dist * 1.8) - spread, 4)
                    results.append((StrategySetupType.FAIR_VALUE_GAP_RETEST, dir_type, price, sl, tp, conf))

        recent_h = max(highs[-20:-1])
        recent_l = min(lows[-20:-1])
        sweep_bull = (lows[-1] < recent_l) and (closes[-1] > recent_l)
        sweep_bear = (highs[-1] > recent_h) and (closes[-1] < recent_h)
        if sweep_bull or sweep_bear:
            dir_type = QuantSignalType.BUY if sweep_bull else QuantSignalType.SELL
            conf = learner.predict_win_probability(features_buy, "BUY" if sweep_bull else "SELL")
            if conf >= 0.72:
                sl_dist = max(bundle.atr * 1.4, spread * 3.0)
                sl = round(price - sl_dist, 4) if sweep_bull else round(price + sl_dist, 4)
                tp = round(price + (sl_dist * 2.2) + spread, 4) if sweep_bull else round(price - (sl_dist * 2.2) - spread, 4)
                results.append((StrategySetupType.LIQUIDITY_SWEEP_REVERSAL, dir_type, price, sl, tp, conf))

        pullback_bull = (price > bundle.ema20) and (abs(price - bundle.ema20) <= (bundle.atr * 0.35)) and (closes[-1] > opens[-1])
        pullback_bear = (price < bundle.ema20) and (abs(bundle.ema20 - price) <= (bundle.atr * 0.35)) and (closes[-1] < opens[-1])
        if (pullback_bull or pullback_bear) and regime in [MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR]:
            dir_type = QuantSignalType.BUY if pullback_bull else QuantSignalType.SELL
            conf = learner.predict_win_probability(features_buy, "BUY" if pullback_bull else "SELL")
            if conf >= 0.65:
                sl_dist = max(bundle.atr * 0.9, spread * 2.5)
                sl = round(price - sl_dist, 4) if pullback_bull else round(price + sl_dist, 4)
                tp = round(price + (sl_dist * 1.6) + spread, 4) if pullback_bull else round(price - (sl_dist * 1.6) - spread, 4)
                results.append((StrategySetupType.EMA_MOMENTUM_PULLBACK, dir_type, price, sl, tp, conf))

        return results

# ═════════════════════════════════════════════════════════════════════════════
# 7. المحرك الرئيسي المنسق
# ═════════════════════════════════════════════════════════════════════════════

class SilverQuantMasterEngine:
    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.feature_engine = SmartFeatureEngine()
        self.learner = AdaptiveBayesianRegimeLearner()
        self.sentiment_engine = MarketSentimentAndOrderFlowEngine(enable_live_network=self.config.enable_auto_network)
        self.spread_guard = SilverSpreadAndRolloverGuard(self.config)
        self.hourly_executor = HourlyFallbackExecutor(self.config)

        self.history_opens: List[float] = []
        self.history_highs: List[float] = []
        self.history_lows: List[float] = []
        self.history_closes: List[float] = []
        self.history_volumes: List[float] = []

        self.open_trades: List[TradeSignal] = []
        self.closed_trades: List[TradeOutcome] = []
        self.account_equity = self.config.account_equity
        self.account_balance = self.config.account_balance
        self.last_session: MarketSession = MarketSession.CLOSED
        self.last_regime: MarketRegime = MarketRegime.MEAN_REVERTING_RANGE

    def ingest_real_candle(self, dt, open_p, high_p, low_p, close_p, volume) -> List[TradeSignal]:
        self.history_opens.append(open_p)
        self.history_highs.append(high_p)
        self.history_lows.append(low_p)
        self.history_closes.append(close_p)
        self.history_volumes.append(volume)

        if len(self.history_closes) > 400:
            self.history_opens.pop(0)
            self.history_highs.pop(0)
            self.history_lows.pop(0)
            self.history_closes.pop(0)
            self.history_volumes.pop(0)

        spread = self.spread_guard.get_spread(dt)
        self._manage_open_trades_with_candle(dt, high_p, low_p, close_p, spread)

        if self.spread_guard.is_blackout(dt) or spread > self.config.max_tolerated_spread:
            return []

        bundle = self.feature_engine.extract_unified_bundle(self.history_highs, self.history_lows, self.history_closes)
        session = MarketSessionManager.get_current_session(dt)
        regime = self.learner.detect_regime(self.history_closes, bundle.atr)
        self.last_session = session
        self.last_regime = regime
        flow_imb, data_src = self.sentiment_engine.get_order_flow_imbalance(
            self.history_highs, self.history_lows, self.history_closes, self.history_opens, self.history_volumes
        )

        new_signals: List[TradeSignal] = []

        hourly_sig = self.hourly_executor.scan_hourly_trade(dt, close_p, bundle, spread, session, regime, self.learner, flow_imb)
        if hourly_sig and len(self.open_trades) < self.config.max_concurrent_trades:
            self.open_trades.append(hourly_sig)
            new_signals.append(hourly_sig)
            logger.info(f"[HourlyEngine] {hourly_sig.strategy.value} | {hourly_sig.signal_type.value} @ {hourly_sig.price}")

        if len(self.open_trades) < self.config.max_concurrent_trades:
            setups = MultiSetupInstitutionalScanner.scan_opportunities(
                self.history_highs, self.history_lows, self.history_closes, self.history_opens,
                bundle, spread, self.learner, flow_imb, regime, session
            )
            for strat, direction, entry, sl, tp, conf in setups:
                if len(self.open_trades) >= self.config.max_concurrent_trades:
                    break
                if any(t.strategy == strat for t in self.open_trades):
                    continue
                risk_amt = self.account_equity * self.config.base_trade_risk_pct
                sl_dist = abs(entry - sl)
                lot = round(risk_amt / max(sl_dist * self.config.silver_contract_size, 1.0), 2)
                lot = max(min(lot, 2.0), 0.01)
                sig = TradeSignal(
                    timestamp=dt, symbol=self.config.symbol, signal_type=direction, strategy=strat,
                    price=entry, stop_loss=sl, take_profit=tp, lot_size=lot, confidence_score=conf,
                    regime=regime, session=session, data_source=data_src
                )
                self.open_trades.append(sig)
                new_signals.append(sig)
                self.hourly_executor.notify_trade(dt)
                logger.info(f"[MultiSetup] {strat.value} | {direction.value} @ {entry}")

        return new_signals

    def _manage_open_trades_with_candle(self, dt, high_p, low_p, close_p, spread):
        remaining = []
        for t in self.open_trades:
            is_buy = (t.signal_type in [QuantSignalType.BUY, QuantSignalType.STRONG_BUY])
            max_favorable = high_p if is_buy else low_p
            profit_dist = (max_favorable - t.price) if is_buy else (t.price - max_favorable)
            target_dist = abs(t.take_profit - t.price)

            if not t.is_breakeven_moved and profit_dist >= (target_dist * 0.50):
                safe_buffer = spread * 1.5
                t.stop_loss = round(t.price + safe_buffer, 4) if is_buy else round(t.price - safe_buffer, 4)
                t.is_breakeven_moved = True

            hit_tp = (high_p >= t.take_profit) if is_buy else (low_p <= t.take_profit)
            hit_sl = (low_p <= t.stop_loss) if is_buy else (high_p >= t.stop_loss)

            if hit_tp or hit_sl:
                exit_p = t.take_profit if hit_tp else t.stop_loss
                diff = (exit_p - t.price) if is_buy else (t.price - exit_p)
                spread_cost = spread * self.config.silver_contract_size * t.lot_size
                net_pnl = (diff * self.config.silver_contract_size * t.lot_size) - spread_cost

                self.account_equity += net_pnl
                self.account_balance += net_pnl

                is_win = (net_pnl > 0)
                bundle = self.feature_engine.extract_unified_bundle(self.history_highs, self.history_lows, self.history_closes)
                feat = self.learner.extract_feature_vector(bundle, exit_p, 0.0)
                self.learner.update_model(feat, "BUY" if is_buy else "SELL", is_win)

                self.closed_trades.append(TradeOutcome(
                    trade_id=f"T_{len(self.closed_trades)+1}", symbol=self.config.symbol,
                    direction=t.signal_type.value, strategy=t.strategy,
                    entry_time=t.timestamp, exit_time=dt, entry_price=t.price, exit_price=exit_p,
                    stop_loss=t.stop_loss, take_profit=t.take_profit, lot_size=t.lot_size,
                    spread_cost=round(spread_cost, 2), pnl_net=round(net_pnl, 2),
                    return_pct=round((net_pnl / self.account_equity) * 100.0, 3),
                    exit_reason="TAKE_PROFIT" if hit_tp else ("BREAKEVEN_PROTECTED" if t.is_breakeven_moved else "STOP_LOSS")
                ))
            else:
                remaining.append(t)
        self.open_trades = remaining

# ═════════════════════════════════════════════════════════════════════════════
# 8. واجهة Kivy (نقطة دخول APK)
# ═════════════════════════════════════════════════════════════════════════════

class StatCard(BoxLayout):
    def __init__(self, label_text, **kwargs):
        super().__init__(orientation='vertical', padding=(10, 8), spacing=2, **kwargs)
        self.label_widget = Label(
            text=label_text, font_size='11sp', size_hint_y=0.4,
            color=(0.55, 0.55, 0.55, 1)
        )
        self.value_widget = Label(
            text="--", font_size='16sp', bold=True, size_hint_y=0.6,
            color=(0.1, 0.1, 0.1, 1)
        )
        self.add_widget(self.label_widget)
        self.add_widget(self.value_widget)

    def set_value(self, text):
        self.value_widget.text = text


class TradeRow(BoxLayout):
    def __init__(self, sig, **kwargs):
        super().__init__(orientation='vertical', size_hint_y=None, height=dp(64),
                          padding=(10, 6), spacing=2, **kwargs)
        top = BoxLayout(orientation='horizontal')
        badge = " [صفقة ساعية إلزامية]" if sig.is_hourly_fallback else ""
        top.add_widget(Label(
            text=f"{sig.strategy.value}{badge}", font_size='12sp', bold=True,
            halign='right', color=(0.15, 0.15, 0.15, 1)
        ))
        top.add_widget(Label(
            text=f"lot {sig.lot_size}", font_size='11sp', size_hint_x=0.3,
            color=(0.4, 0.4, 0.4, 1)
        ))
        bottom = BoxLayout(orientation='horizontal')
        bottom.add_widget(Label(
            text=f"{sig.signal_type.value} @ {sig.price}",
            font_size='11sp', color=(0.35, 0.35, 0.35, 1)
        ))
        bottom.add_widget(Label(
            text=f"SL {sig.stop_loss} | TP {sig.take_profit} | ثقة {sig.confidence_score*100:.0f}%",
            font_size='11sp', size_hint_x=1.4, color=(0.5, 0.5, 0.5, 1)
        ))
        self.add_widget(top)
        self.add_widget(bottom)


class SilverQuantRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=dp(12), spacing=dp(8), **kwargs)
        self.engine = SilverQuantMasterEngine(EngineConfig())

        self.price = 31.50
        self.sim_time = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)
        self.tick_count = 0

        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50))
        header.add_widget(Label(
            text="[b]SilverQuant v8.8[/b]\nXAGUSD", markup=True, font_size='16sp',
            halign='right', color=(0.1, 0.1, 0.1, 1)
        ))
        self.status_label = Label(
            text="EMPIRICAL_MICROSTRUCTURE_FLOW", font_size='10sp',
            color=(0.8, 0.5, 0.1, 1), halign='left'
        )
        header.add_widget(self.status_label)
        self.add_widget(header)

        grid = GridLayout(cols=2, size_hint_y=None, height=dp(140), spacing=dp(6))
        self.card_equity = StatCard("equity")
        self.card_balance = StatCard("balance")
        self.card_session = StatCard("session")
        self.card_regime = StatCard("regime")
        for c in (self.card_equity, self.card_balance, self.card_session, self.card_regime):
            grid.add_widget(c)
        self.add_widget(grid)

        self.add_widget(Label(
            text="الصفقات المفتوحة", size_hint_y=None, height=dp(24),
            font_size='13sp', color=(0.3, 0.3, 0.3, 1)
        ))

        self.trades_scroll = ScrollView(size_hint_y=0.4)
        self.trades_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6))
        self.trades_box.bind(minimum_height=self.trades_box.setter('height'))
        self.trades_scroll.add_widget(self.trades_box)
        self.add_widget(self.trades_scroll)

        self.add_widget(Label(
            text="آخر إشارات مغلقة", size_hint_y=None, height=dp(24),
            font_size='13sp', color=(0.3, 0.3, 0.3, 1)
        ))
        self.closed_label = Label(
            text="لا توجد صفقات مغلقة بعد", size_hint_y=0.3,
            font_size='11sp', color=(0.45, 0.45, 0.45, 1), valign='top'
        )
        self.add_widget(self.closed_label)

        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.toggle_btn = Button(text="إيقاف التغذية اللحظية")
        self.toggle_btn.bind(on_press=self.toggle_feed)
        btn_row.add_widget(self.toggle_btn)
        self.add_widget(btn_row)

        self._running = True
        Clock.schedule_interval(self.tick, 2.0)

    def toggle_feed(self, instance):
        self._running = not self._running
        self.toggle_btn.text = "استئناف التغذية اللحظية" if not self._running else "إيقاف التغذية اللحظية"

    def _next_synthetic_candle(self):
        """
        شمعة تجريبية للعرض عند عدم وجود اتصال حي بمصدر بيانات فعلي.
        يجب استبدال هذه الدالة ببيانات وسيط حقيقي (MT5/API) قبل أي استخدام فعلي.
        """
        z = random.gauss(0.0, 1.0)
        self.price = max(round(self.price * math.exp(0.0002 * z), 4), 5.0)
        o = self.price
        h = o + abs(random.gauss(0.0, 0.05))
        l = o - abs(random.gauss(0.0, 0.05))
        c = o + random.gauss(0.0, 0.03)
        v = max(int(random.gauss(1200, 300)), 100)
        self.sim_time += timedelta(minutes=1)
        return self.sim_time, o, h, l, c, v

    def tick(self, dt):
        if not self._running:
            return

        candle_dt, o, h, l, c, v = self._next_synthetic_candle()
        signals = self.engine.ingest_real_candle(candle_dt, o, h, l, c, v)

        self.card_equity.set_value(f"${self.engine.account_equity:,.2f}")
        self.card_balance.set_value(f"${self.engine.account_balance:,.2f}")
        self.card_session.set_value(self.engine.last_session.value)
        self.card_regime.set_value(self.engine.last_regime.value)

        if self.engine.sentiment_engine.is_connected:
            self.status_label.text = "LIVE_NETWORK_FEED"
            self.status_label.color = (0.1, 0.6, 0.3, 1)
        else:
            self.status_label.text = "EMPIRICAL_MICROSTRUCTURE_FLOW"
            self.status_label.color = (0.8, 0.5, 0.1, 1)

        self.trades_box.clear_widgets()
        for sig in reversed(self.engine.open_trades):
            self.trades_box.add_widget(TradeRow(sig))
        if not self.engine.open_trades:
            self.trades_box.add_widget(Label(
                text="لا توجد صفقات مفتوحة حالياً", size_hint_y=None, height=dp(40),
                font_size='11sp', color=(0.5, 0.5, 0.5, 1)
            ))

        if self.engine.closed_trades:
            last5 = self.engine.closed_trades[-5:]
            lines = [
                f"{t.strategy.value} | {t.direction} | صافي {t.pnl_net:+.2f}$ | {t.exit_reason}"
                for t in reversed(last5)
            ]
            self.closed_label.text = "\n".join(lines)


class SilverQuantApp(App):
    def build(self):
        Window.clearcolor = (0.97, 0.97, 0.96, 1)
        return SilverQuantRoot()


if __name__ == "__main__":
    SilverQuantApp().run()

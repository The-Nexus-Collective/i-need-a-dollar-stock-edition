#!/usr/bin/env python3

import os
import logging
import time
import schedule
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import pytz
import ccxt
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Local imports
from db import db_manager, SentimentData, Trade

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
TOP_COINS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'BNB', 'ADA', 'AVAX', 'TRX', 'LINK']
BINANCE_SYMBOLS = [f'{coin}/USDT' for coin in TOP_COINS]
RISK_PERCENTAGE = 0.02  # 2% risk per trade
STOP_MULTIPLIER = 1.5  # 1.5x ATR for stop loss
TARGET_MULTIPLIER = 4.0  # 4x ATR for take profit
INITIAL_EQUITY = 10000.0  # Starting equity for paper trading

class GrokAPI:
    """Grok API integration for sentiment analysis"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"

    def get_sentiment(self, coin: str) -> Tuple[float, float, str]:
        """
        Get sentiment score and narrative strength for a coin
        Returns: (sentiment_score, narrative_strength, raw_response)
        """
        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            prompt = f"sentiment –100/+100 + narrative 0–100 for {coin}, one line"

            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "model": "grok-beta",
                "stream": False,
                "temperature": 0.1
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                raw_response = data['choices'][0]['message']['content']

                # Parse the response - expecting format like "BTC: sentiment -45, narrative 78"
                # This is a simplified parser - you may need to adjust based on actual Grok response format
                try:
                    # Extract numbers from response
                    parts = raw_response.replace(',', '').split()
                    sentiment = None
                    narrative = None

                    for i, part in enumerate(parts):
                        if part in ['sentiment', 'sent']:
                            try:
                                sentiment = float(parts[i+1])
                            except (ValueError, IndexError):
                                continue
                        elif part in ['narrative', 'narr']:
                            try:
                                narrative = float(parts[i+1])
                            except (ValueError, IndexError):
                                continue

                    if sentiment is None or narrative is None:
                        # Fallback: try to extract any numbers
                        import re
                        numbers = re.findall(r'-?\d+\.?\d*', raw_response)
                        if len(numbers) >= 2:
                            sentiment = float(numbers[0])
                            narrative = float(numbers[1])
                        else:
                            raise ValueError("Could not parse sentiment and narrative")

                    # Ensure ranges are correct
                    sentiment = max(-100, min(100, sentiment))
                    narrative = max(0, min(100, narrative))

                    return sentiment, narrative, raw_response

                except Exception as e:
                    logger.error(f"Failed to parse Grok response for {coin}: {raw_response}")
                    raise e
            else:
                raise Exception(f"Grok API error: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error getting sentiment for {coin}: {str(e)}")
            raise e

class BinanceData:
    """Binance public API integration for market data"""

    def __init__(self):
        self.exchange = ccxt.binance()
        self.exchange.load_markets()

    def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {str(e)}")
            raise e

    def get_atr(self, symbol: str, timeframe: str = '1h', periods: int = 14) -> float:
        """
        Calculate ATR (Average True Range) for a symbol
        """
        try:
            # Get historical OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=periods + 1)
            if len(ohlcv) < periods:
                raise ValueError(f"Insufficient data for ATR calculation: {len(ohlcv)} bars")

            # Calculate True Range
            tr_values = []
            for i in range(1, len(ohlcv)):
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i-1][4]

                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)

            # Calculate ATR as simple moving average
            atr = np.mean(tr_values)
            return float(atr)

        except Exception as e:
            logger.error(f"Error calculating ATR for {symbol}: {str(e)}")
            raise e

class SentimentBot:
    """Main sentiment trading bot"""

    def __init__(self):
        self.grok_api = GrokAPI(os.getenv('XAI_API_KEY', ''))
        self.binance = BinanceData()
        self.mode = os.getenv('MODE', 'paper').lower()
        self.equity = INITIAL_EQUITY
        self.cash = INITIAL_EQUITY
        self.positions = {}  # coin -> position info

        # Initialize database
        db_manager.create_tables()

        logger.info(f"Bot initialized in {self.mode} mode with ${self.equity} equity")

    def get_sentiment_scores(self) -> Dict[str, Dict]:
        """
        Get sentiment scores for all coins from Grok
        Returns: {coin: {'sentiment': float, 'narrative': float, 'combined_score': float, 'sentiment_id': int}}
        """
        results = {}

        for coin in TOP_COINS:
            try:
                sentiment, narrative, raw_response = self.grok_api.get_sentiment(coin)
                combined_score = sentiment * (narrative / 100)

                # Create hash for deduplication
                response_hash = hashlib.sha256(raw_response.encode()).hexdigest()

                # Save to database
                sentiment_data = db_manager.save_sentiment_data(
                    coin=coin,
                    sentiment_score=sentiment,
                    narrative_strength=narrative,
                    grok_response=raw_response,
                    response_hash=response_hash
                )

                results[coin] = {
                    'sentiment': sentiment,
                    'narrative': narrative,
                    'combined_score': combined_score,
                    'sentiment_id': sentiment_data.id
                }

                logger.info(f"{coin}: sentiment={sentiment:.1f}, narrative={narrative:.1f}, score={combined_score:.1f}")

            except Exception as e:
                logger.error(f"Failed to get sentiment for {coin}: {str(e)}")
                continue

        return results

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """
        Calculate position size based on risk percentage
        """
        risk_amount = self.equity * RISK_PERCENTAGE
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = risk_amount / risk_per_unit
        return quantity

    def execute_trade(self, coin: str, side: str, sentiment_data: Dict):
        """
        Execute a trade in paper mode
        """
        symbol = f"{coin}/USDT"

        try:
            # Get market data
            entry_price = self.binance.get_current_price(symbol)
            atr_value = self.binance.get_atr(symbol)

            # Calculate stop loss and take profit
            if side == 'long':
                stop_loss = entry_price - (atr_value * STOP_MULTIPLIER)
                take_profit = entry_price + (atr_value * TARGET_MULTIPLIER)
            else:  # short
                stop_loss = entry_price + (atr_value * STOP_MULTIPLIER)
                take_profit = entry_price - (atr_value * TARGET_MULTIPLIER)

            # Calculate position size
            quantity = self.calculate_position_size(entry_price, stop_loss)

            # Check if we have enough cash
            position_value = quantity * entry_price
            if position_value > self.cash:
                logger.warning(f"Insufficient cash for {coin} trade: need ${position_value:.2f}, have ${self.cash:.2f}")
                return

            # Save trade to database
            trade = db_manager.save_trade(
                coin=coin,
                side=side,
                entry_price=entry_price,
                quantity=quantity,
                atr_value=atr_value,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_sentiment_id=sentiment_data['sentiment_id'],
                is_paper_trade=(self.mode == 'paper')
            )

            # Update portfolio
            self.cash -= position_value
            self.positions[coin] = {
                'trade_id': trade.id,
                'side': side,
                'entry_price': entry_price,
                'quantity': quantity,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'atr_value': atr_value
            }

            logger.info(f"PAPER TRADE: {side.upper()} {coin} {quantity:.4f} @ ${entry_price:.2f} | SL: ${stop_loss:.2f} | TP: ${take_profit:.2f}")

        except Exception as e:
            logger.error(f"Error executing trade for {coin}: {str(e)}")

    def check_positions(self):
        """
        Check open positions for stop loss / take profit hits
        """
        for coin, position in list(self.positions.items()):
            try:
                symbol = f"{coin}/USDT"
                current_price = self.binance.get_current_price(symbol)

                trade_id = position['trade_id']
                side = position['side']
                entry_price = position['entry_price']
                quantity = position['quantity']
                stop_loss = position['stop_loss']
                take_profit = position['take_profit']

                exit_reason = None
                exit_price = current_price

                if side == 'long':
                    if current_price <= stop_loss:
                        exit_reason = 'stop_loss'
                    elif current_price >= take_profit:
                        exit_reason = 'take_profit'
                else:  # short
                    if current_price >= stop_loss:
                        exit_reason = 'stop_loss'
                    elif current_price <= take_profit:
                        exit_reason = 'take_profit'

                if exit_reason:
                    # Calculate PnL
                    if side == 'long':
                        pnl = (exit_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - exit_price) * quantity

                    pnl_percent = (pnl / (entry_price * quantity)) * 100

                    # Update portfolio
                    self.cash += (quantity * exit_price)
                    self.equity = self.cash + sum(
                        pos['quantity'] * self.binance.get_current_price(f"{coin}/USDT")
                        for coin, pos in self.positions.items() if coin != coin  # exclude current position
                    )

                    # Update database
                    db_manager.update_trade_exit(
                        trade_id=trade_id,
                        exit_price=exit_price,
                        pnl=pnl,
                        pnl_percent=pnl_percent,
                        status='closed',
                        close_reason=exit_reason
                    )

                    # Remove from positions
                    del self.positions[coin]

                    logger.info(f"CLOSED {coin}: {exit_reason.upper()} | PnL: ${pnl:.2f} ({pnl_percent:.2f}%)")

            except Exception as e:
                logger.error(f"Error checking position for {coin}: {str(e)}")

    def flatten_all_positions(self):
        """
        Flatten all positions at end of day
        """
        for coin, position in list(self.positions.items()):
            try:
                symbol = f"{coin}/USDT"
                current_price = self.binance.get_current_price(symbol)

                trade_id = position['trade_id']
                side = position['side']
                entry_price = position['entry_price']
                quantity = position['quantity']

                # Calculate PnL
                if side == 'long':
                    pnl = (current_price - entry_price) * quantity
                else:
                    pnl = (entry_price - current_price) * quantity

                pnl_percent = (pnl / (entry_price * quantity)) * 100

                # Update portfolio
                position_value = quantity * current_price
                self.cash += position_value

                # Update database
                db_manager.update_trade_exit(
                    trade_id=trade_id,
                    exit_price=current_price,
                    pnl=pnl,
                    pnl_percent=pnl_percent,
                    status='closed',
                    close_reason='end_of_day'
                )

                # Remove from positions
                del self.positions[coin]

                logger.info(f"FLATTENED {coin}: EOD | PnL: ${pnl:.2f} ({pnl_percent:.2f}%)")

            except Exception as e:
                logger.error(f"Error flattening position for {coin}: {str(e)}")

    def run_trading_cycle(self):
        """
        Main trading cycle: get sentiments, find best opportunity, execute trade
        """
        try:
            logger.info("Starting trading cycle...")

            # Get sentiment scores
            sentiment_scores = self.get_sentiment_scores()
            if not sentiment_scores:
                logger.warning("No sentiment data received, skipping trading cycle")
                return

            # Find the coin with highest absolute combined score
            best_coin = None
            best_score = 0
            best_data = None

            for coin, data in sentiment_scores.items():
                abs_score = abs(data['combined_score'])
                if abs_score > best_score:
                    best_score = abs_score
                    best_coin = coin
                    best_data = data

            if not best_coin or best_score < 10:  # Minimum threshold for trading
                logger.info(f"No strong signals found. Best: {best_coin} score: {best_score:.1f}")
                return

            # Determine trade direction
            if best_data['combined_score'] > 0:
                side = 'long'
            else:
                side = 'short'

            # Check if we already have a position in this coin
            if best_coin in self.positions:
                current_side = self.positions[best_coin]['side']
                if current_side == side:
                    logger.info(f"Already have {side} position in {best_coin}, skipping")
                    return
                else:
                    # Close existing position first
                    logger.info(f"Closing existing {current_side} position in {best_coin} to open {side}")
                    # The position will be closed by check_positions if stop/target hit
                    # For now, we'll skip if we have conflicting position
                    return

            # Execute trade
            logger.info(f"Executing {side} trade for {best_coin} (score: {best_data['combined_score']:.1f})")
            self.execute_trade(best_coin, side, best_data)

            # Check existing positions
            self.check_positions()

            # Save portfolio snapshot
            positions_value = sum(
                pos['quantity'] * self.binance.get_current_price(f"{coin}/USDT")
                for coin, pos in self.positions.items()
            )
            total_trades = len(db_manager.get_open_trades()) + len([t for t in db_manager.get_session().query(Trade).all() if t.status == 'closed'])
            winning_trades = len([t for t in db_manager.get_session().query(Trade).all() if t.status == 'closed' and t.pnl > 0])
            losing_trades = len([t for t in db_manager.get_session().query(Trade).all() if t.status == 'closed' and t.pnl < 0])

            db_manager.save_portfolio_snapshot(
                equity=self.equity,
                cash=self.cash,
                positions_value=positions_value,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades
            )

            logger.info(f"Trading cycle completed. Equity: ${self.equity:.2f}")

        except Exception as e:
            logger.error(f"Error in trading cycle: {str(e)}")

    def is_end_of_day(self) -> bool:
        """
        Check if it's time to flatten positions (23:55 CET)
        """
        cet = pytz.timezone('CET')
        now = datetime.now(cet)
        return now.hour == 23 and now.minute >= 55

def main():
    """Main function"""
    bot = SentimentBot()

    # Schedule trading cycle every hour
    schedule.every().hour.do(bot.run_trading_cycle)

    # Schedule end-of-day flatten at 23:55 CET
    schedule.every().day.at("23:55", "CET").do(bot.flatten_all_positions)

    logger.info("Bot started. Running every hour...")

    # Run initial cycle
    bot.run_trading_cycle()

    # Main loop
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()

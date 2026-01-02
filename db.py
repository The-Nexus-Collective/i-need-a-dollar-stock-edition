from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

class SentimentData(Base):
    """Store raw sentiment data from Grok API"""
    __tablename__ = 'sentiment_data'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    coin = Column(String(10), nullable=False)
    sentiment_score = Column(Float, nullable=False)  # -100 to +100
    narrative_strength = Column(Float, nullable=False)  # 0 to 100
    combined_score = Column(Float, nullable=False)  # sentiment * (strength/100)
    grok_response = Column(Text, nullable=False)  # Raw API response
    response_hash = Column(String(64), nullable=False)  # SHA256 hash for deduplication

class Trade(Base):
    """Store trade records"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    coin = Column(String(10), nullable=False)
    side = Column(String(4), nullable=False)  # 'long' or 'short'
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    atr_value = Column(Float, nullable=False)  # ATR at entry
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    entry_sentiment_id = Column(Integer, nullable=False)  # FK to sentiment_data
    exit_sentiment_id = Column(Integer, nullable=True)  # FK to sentiment_data if closed by signal
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    status = Column(String(20), nullable=False)  # 'open', 'closed', 'stopped', 'target_hit'
    close_reason = Column(String(50), nullable=True)
    close_timestamp = Column(DateTime, nullable=True)
    is_paper_trade = Column(Boolean, default=True, nullable=False)

class PortfolioSnapshot(Base):
    """Store portfolio snapshots for equity curve"""
    __tablename__ = 'portfolio_snapshots'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    equity = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False)
    total_trades = Column(Integer, nullable=False)
    winning_trades = Column(Integer, nullable=False)
    losing_trades = Column(Integer, nullable=False)

class DatabaseManager:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 'postgresql://sentiment_user:sentiment_pass@localhost:5432/sentiment_bot')
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created successfully")

    def get_session(self):
        """Get database session"""
        return self.SessionLocal()

    def save_sentiment_data(self, coin: str, sentiment_score: float, narrative_strength: float,
                           grok_response: str, response_hash: str) -> SentimentData:
        """Save sentiment data to database"""
        combined_score = sentiment_score * (narrative_strength / 100)

        sentiment = SentimentData(
            coin=coin,
            sentiment_score=sentiment_score,
            narrative_strength=narrative_strength,
            combined_score=combined_score,
            grok_response=grok_response,
            response_hash=response_hash
        )

        with self.get_session() as session:
            session.add(sentiment)
            session.commit()
            session.refresh(sentiment)

        logger.info(f"Saved sentiment data for {coin}: score={combined_score}")
        return sentiment

    def save_trade(self, coin: str, side: str, entry_price: float, quantity: float,
                  atr_value: float, stop_loss: float, take_profit: float,
                  entry_sentiment_id: int, is_paper_trade: bool = True) -> Trade:
        """Save new trade to database"""
        trade = Trade(
            coin=coin,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            atr_value=atr_value,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_sentiment_id=entry_sentiment_id,
            status='open',
            is_paper_trade=is_paper_trade
        )

        with self.get_session() as session:
            session.add(trade)
            session.commit()
            session.refresh(trade)

        logger.info(f"Saved {side} trade for {coin}: qty={quantity}, entry={entry_price}")
        return trade

    def update_trade_exit(self, trade_id: int, exit_price: float, pnl: float,
                         pnl_percent: float, status: str, close_reason: str,
                         exit_sentiment_id: Optional[int] = None):
        """Update trade with exit information"""
        with self.get_session() as session:
            trade = session.query(Trade).filter(Trade.id == trade_id).first()
            if trade:
                trade.exit_price = exit_price
                trade.pnl = pnl
                trade.pnl_percent = pnl_percent
                trade.status = status
                trade.close_reason = close_reason
                trade.close_timestamp = datetime.utcnow()
                if exit_sentiment_id:
                    trade.exit_sentiment_id = exit_sentiment_id

                session.commit()
                logger.info(f"Updated trade {trade_id}: {status} - PnL: {pnl}")
            else:
                logger.error(f"Trade {trade_id} not found for update")

    def get_open_trades(self) -> list[Trade]:
        """Get all open trades"""
        with self.get_session() as session:
            return session.query(Trade).filter(Trade.status == 'open').all()

    def get_recent_sentiments(self, limit: int = 100) -> list[SentimentData]:
        """Get recent sentiment data"""
        with self.get_session() as session:
            return session.query(SentimentData).order_by(
                SentimentData.timestamp.desc()
            ).limit(limit).all()

    def get_portfolio_history(self, limit: int = 1000) -> list[PortfolioSnapshot]:
        """Get portfolio snapshot history"""
        with self.get_session() as session:
            return session.query(PortfolioSnapshot).order_by(
                PortfolioSnapshot.timestamp.desc()
            ).limit(limit).all()

    def save_portfolio_snapshot(self, equity: float, cash: float, positions_value: float,
                               total_trades: int, winning_trades: int, losing_trades: int):
        """Save portfolio snapshot"""
        snapshot = PortfolioSnapshot(
            equity=equity,
            cash=cash,
            positions_value=positions_value,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades
        )

        with self.get_session() as session:
            session.add(snapshot)
            session.commit()

# Global database instance
db_manager = DatabaseManager()

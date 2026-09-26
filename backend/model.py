import datetime

from sqlalchemy import create_engine, String, select, DateTime, Float, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

engine = create_engine("sqlite:///stocks.db")

class Base(DeclarativeBase):
    pass

class LatestStockPrices(Base):
    __tablename__ = "latest_stock_prices"
    
    symbol: Mapped[str] = mapped_column(String(5), primary_key=True)
    
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    open: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume_weighted_price: Mapped[float] = mapped_column(Float)
    
    number_of_trades: Mapped[int] = mapped_column(Integer)
    volume: Mapped[int] = mapped_column(Integer)
    
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime)
    
Base.metadata.create_all(engine)

db = Session(engine)
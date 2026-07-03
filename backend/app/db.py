import logging
from sqlalchemy import create_engine, text, Column, String, DateTime, Date, Float, PrimaryKeyConstraint
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger("quantforge.db")
logging.basicConfig(level=logging.INFO)

Base = declarative_base()

# SQLAlchemy Database Models
class SpotPrice(Base):
    __tablename__ = "spot_prices"
    timestamp = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String(20), nullable=False)
    price = Column(Float, nullable=False)
    
    __table_args__ = (
        PrimaryKeyConstraint("timestamp", "symbol"),
    )

class OptionChain(Base):
    __tablename__ = "option_chain"
    timestamp = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String(20), nullable=False)
    expiry_date = Column(Date, nullable=False)
    strike_price = Column(Float, nullable=False)
    option_type = Column(String(2), nullable=False)  # 'CE' or 'PE'
    open_interest = Column(Float, default=0.0)
    change_in_oi = Column(Float, default=0.0)
    volume = Column(Float, default=0.0)
    implied_volatility = Column(Float, default=0.0)
    last_price = Column(Float, default=0.0)
    bid_price = Column(Float, default=0.0)
    ask_price = Column(Float, default=0.0)
    
    # Greeks fields
    delta = Column(Float, default=0.0)
    gamma = Column(Float, default=0.0)
    vega = Column(Float, default=0.0)
    theta = Column(Float, default=0.0)

    __table_args__ = (
        PrimaryKeyConstraint("timestamp", "symbol", "expiry_date", "strike_price", "option_type"),
    )

class VixData(Base):
    __tablename__ = "vix_data"
    timestamp = Column(DateTime(timezone=True), nullable=False)
    value = Column(Float, nullable=False)
    
    __table_args__ = (
        PrimaryKeyConstraint("timestamp"),
    )

class FuturePrice(Base):
    __tablename__ = "future_prices"
    timestamp = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String(20), nullable=False)
    price = Column(Float, nullable=False)
    
    __table_args__ = (
        PrimaryKeyConstraint("timestamp", "symbol"),
    )

class FiiDiiActivity(Base):
    __tablename__ = "fii_dii_activity"
    timestamp = Column(DateTime(timezone=True), nullable=False)
    fii_net = Column(Float, default=0.0)  # in Crores
    dii_net = Column(Float, default=0.0)  # in Crores
    
    __table_args__ = (
        PrimaryKeyConstraint("timestamp"),
    )

class AlertLog(Base):
    __tablename__ = "alert_logs"
    id = Column(String(50), primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String(20), nullable=False)
    alert_type = Column(String(50), nullable=False)  # PCR, VIX, OI, etc.
    message = Column(String(250), nullable=False)
    channel = Column(String(20), default="ALL")  # Telegram, Email, WhatsApp

class PredictionLog(Base):
    __tablename__ = "prediction_logs"
    timestamp = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String(20), nullable=False)
    bull_prob = Column(Float, nullable=False)
    bear_prob = Column(Float, nullable=False)
    neutral_prob = Column(Float, nullable=False)
    regime = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    reasons = Column(String(500), nullable=False)  # JSON-encoded list
    
    __table_args__ = (
        PrimaryKeyConstraint("timestamp", "symbol"),
    )

# Global database parameters
engine = None
SessionLocal = None
is_postgres = False

def init_db():
    global engine, SessionLocal, is_postgres
    
    pg_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    pg_default_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/postgres"
    
    # 1. Attempt PostgreSQL connection
    try:
        logger.info(f"Connecting to PostgreSQL default database to ensure '{settings.POSTGRES_DB}' exists...")
        # Timeout quickly to avoid hanging
        temp_engine = create_engine(pg_default_url, connect_args={"connect_timeout": 2})
        with temp_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{settings.POSTGRES_DB}'"))
            if not result.fetchone():
                logger.info(f"Database '{settings.POSTGRES_DB}' not found. Creating database...")
                # autocommit execution
                conn.execute(text("commit"))
                conn.execute(text(f"CREATE DATABASE {settings.POSTGRES_DB}"))
                logger.info(f"Database '{settings.POSTGRES_DB}' created successfully.")
        temp_engine.dispose()
        
        # Connect to newly created/verified target db
        engine = create_engine(pg_url, connect_args={"connect_timeout": 2})
        # Test connection
        with engine.connect() as conn:
            pass
        is_postgres = True
        logger.info("Successfully established connection to PostgreSQL.")
        
    except Exception as pg_err:
        logger.warning(f"PostgreSQL connection/creation failed: {pg_err}. Initializing SQLite fallback database...")
        try:
            # Connect to SQLite fallback database
            engine = create_engine(settings.SQLITE_DATABASE_PATH, connect_args={"check_same_thread": False})
            with engine.connect() as conn:
                pass
            is_postgres = False
            logger.info("Successfully established connection to fallback SQLite database.")
        except Exception as sqlite_err:
            logger.error(f"Failed to initialize fallback SQLite: {sqlite_err}")
            raise sqlite_err

    # Create SessionMaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables
    logger.info("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    # If PostgreSQL, try creating TimescaleDB hypertables
    if is_postgres:
        try:
            with engine.connect() as conn:
                conn.execute(text("commit"))
                # Check if TimescaleDB extension is available
                ext_check = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"))
                if ext_check.fetchone():
                    logger.info("TimescaleDB extension is present. Converting tables to hypertables...")
                    
                    # Convert tables to hypertables if they aren't already
                    for table in ["spot_prices", "option_chain", "vix_data", "future_prices", "fii_dii_activity", "prediction_logs"]:
                        try:
                            conn.execute(text(f"SELECT create_hypertable('{table}', 'timestamp', if_not_exists => TRUE);"))
                            logger.info(f"Hypertable created for {table}")
                        except Exception as e:
                            logger.warning(f"Could not convert {table} to hypertable: {e}")
                else:
                    logger.info("TimescaleDB extension not loaded. Running with standard PostgreSQL tables.")
        except Exception as ext_err:
            logger.warning(f"Error checking TimescaleDB capabilities: {ext_err}. Running with standard tables.")

def get_db():
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

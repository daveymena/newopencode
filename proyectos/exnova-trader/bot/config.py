"""
Configuración centralizada del bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Clase de configuración centralizada"""
    
    _json_config = None

    @classmethod
    def _load_json(cls):
        if cls._json_config is not None:
            return
        import json
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(bot_dir, "bot_config.json")
        if os.path.exists(json_path):
            try:
                with open(json_path) as f:
                    cls._json_config = json.load(f)
            except Exception:
                cls._json_config = {}
        else:
            cls._json_config = {}

    @classmethod
    def get(cls, key, default=None):
        """Busca en bot_config.json primero, luego en os.environ."""
        cls._load_json()
        # Mapeo de claves de main.py a rutas en el JSON
        mapping = {
            "ASSETS": ("assets",),
            "INITIAL_BALANCE": ("backtest_settings", "initial_balance"),
            "MIN_CONFIDENCE": ("limits", "min_confidence"),
            "TRADE_AMOUNT_PCT": ("risk", "position_size_pct"),
            "COOLDOWN_AFTER_LOSS": ("limits", "cooldown_after_loss"),
            "MIN_BETWEEN_TRADES": ("limits", "min_between_trades"),
            "MAX_CONSEC_LOSSES": ("limits", "stop_after_consecutive_losses"),
            "MAX_TRADES_PER_HOUR": ("limits", "max_trades_per_hour"),
        }
        path = mapping.get(key)
        if path:
            val = cls._json_config
            try:
                for p in path:
                    val = val.get(p, {})
                if val != {} and val is not None:
                    return val
            except Exception:
                pass
        # Fallback a variable de entorno
        env_key = key
        env_val = os.getenv(env_key)
        if env_val is not None:
            return env_val
        return default
    
    # ============= BROKER =============
    BROKER_NAME = os.getenv("BROKER_NAME", "exnova")
    ACCOUNT_TYPE = os.getenv("ACCOUNT_TYPE", "PRACTICE")
    
    # Credenciales Exnova
    EXNOVA_EMAIL = os.getenv("EXNOVA_EMAIL", "")
    EXNOVA_PASSWORD = os.getenv("EXNOVA_PASSWORD", "")
    
    # Alias de compatibilidad
    EX_EMAIL = EXNOVA_EMAIL
    EX_PASSWORD = EXNOVA_PASSWORD
    
    # Credenciales IQ Option
    IQ_OPTION_EMAIL = os.getenv("IQ_OPTION_EMAIL", "")
    IQ_OPTION_PASSWORD = os.getenv("IQ_OPTION_PASSWORD", "")

    # ============= TELEGRAM =============
    TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '')
    TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE', '')
    TELEGRAM_SESSION_NAME = os.getenv('TELEGRAM_SESSION_NAME', 'trading_session')
    TELEGRAM_CHATS = os.getenv('TELEGRAM_CHATS', '').split(',') if os.getenv('TELEGRAM_CHATS') else []
    
    # ============= TRADING =============
    DEFAULT_ASSET = os.getenv("DEFAULT_ASSET", "EURUSD-OTC")
    CAPITAL_PER_TRADE = float(os.getenv("CAPITAL_PER_TRADE", "1"))
    EXPIRATION_TIME = int(os.getenv("EXPIRATION_TIME", "60"))
    TIMEFRAME = 60  # Timeframe en segundos (1 minuto por defecto)
    
    # Expiración automática vs manual
    AUTO_EXPIRATION = True  # Por defecto, IA decide
    MANUAL_EXPIRATION = 3   # Default a 3 minutos (mejor estabilidad)
    
    # Rango permitido para expiración IA (2-5 min)
    MIN_EXPIRATION_TIME = 2
    MAX_EXPIRATION_TIME = 5
    
    # ============= RISK MANAGEMENT =============
    MAX_MARTINGALE = int(os.getenv("MAX_MARTINGALE", "0"))
    STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "20"))
    TAKE_PROFIT_PERCENT = float(os.getenv("TAKE_PROFIT_PERCENT", "10"))
    
    # ============= HORARIO DE OPERACIÓN =============
    TRADING_START_HOUR = int(os.getenv("TRADING_START_HOUR", "0"))  # 00:00 AM
    TRADING_END_HOUR = int(os.getenv("TRADING_END_HOUR", "23"))      # 23:59 PM
    TRADING_END_MINUTE = int(os.getenv("TRADING_END_MINUTE", "59"))
    MIN_VOLATILITY_TO_START = float(os.getenv("MIN_VOLATILITY_TO_START", "0.05"))  # ATR mínimo para iniciar
    
    # ============= AI/LLM =============
    USE_LLM = os.getenv("USE_LLM", "True").lower() == "true"
    
    # OpenRouter (IA principal - modelos gratuitos)
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
    
    # NVIDIA NIM (API directa)
    NVIDIA_NIM_BRIDGE_URL = os.getenv("NVIDIA_NIM_BRIDGE_URL", "https://integrate.api.nvidia.com/v1")
    NVIDIA_NIM_BRIDGE_API_KEY = os.getenv("NVIDIA_NIM_BRIDGE_API_KEY", "")
    NVIDIA_NIM_BRIDGE_MODEL = os.getenv("NVIDIA_NIM_BRIDGE_MODEL", "meta/llama-3.1-8b-instruct")
    
    # GitHub Models (Azure AI Inference)
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_MODEL = os.getenv("GITHUB_MODEL", "gpt-4o")
    GITHUB_MODEL_CLAUDE = os.getenv("GITHUB_MODEL_CLAUDE", "claude-sonnet-4-20250514")
    
    # ============= BACKEND (para GUI remota) =============
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    # ============= PATHS =============
    DATA_DIR = "data"
    MODELS_DIR = "models"
    EXPERIENCES_FILE = os.path.join(DATA_DIR, "experiences.json")
    MODEL_PATH = os.path.join(MODELS_DIR, "rl_agent")

# Mantener compatibilidad con imports directos
BROKER_NAME = Config.BROKER_NAME
ACCOUNT_TYPE = Config.ACCOUNT_TYPE
EXNOVA_EMAIL = Config.EXNOVA_EMAIL
EXNOVA_PASSWORD = Config.EXNOVA_PASSWORD
IQ_OPTION_EMAIL = Config.IQ_OPTION_EMAIL
IQ_OPTION_PASSWORD = Config.IQ_OPTION_PASSWORD
DEFAULT_ASSET = Config.DEFAULT_ASSET
CAPITAL_PER_TRADE = Config.CAPITAL_PER_TRADE
EXPIRATION_TIME = Config.EXPIRATION_TIME
TIMEFRAME = Config.TIMEFRAME
MAX_MARTINGALE = Config.MAX_MARTINGALE
STOP_LOSS_PERCENT = Config.STOP_LOSS_PERCENT
TAKE_PROFIT_PERCENT = Config.TAKE_PROFIT_PERCENT
TRADING_START_HOUR = Config.TRADING_START_HOUR
TRADING_END_HOUR = Config.TRADING_END_HOUR
TRADING_END_MINUTE = Config.TRADING_END_MINUTE
MIN_VOLATILITY_TO_START = Config.MIN_VOLATILITY_TO_START
USE_LLM = Config.USE_LLM
OPENROUTER_API_KEY = Config.OPENROUTER_API_KEY
OPENROUTER_MODEL = Config.OPENROUTER_MODEL
NVIDIA_NIM_BRIDGE_URL = Config.NVIDIA_NIM_BRIDGE_URL
NVIDIA_NIM_BRIDGE_API_KEY = Config.NVIDIA_NIM_BRIDGE_API_KEY
NVIDIA_NIM_BRIDGE_MODEL = Config.NVIDIA_NIM_BRIDGE_MODEL
GITHUB_TOKEN = Config.GITHUB_TOKEN
GITHUB_MODEL = Config.GITHUB_MODEL
GITHUB_MODEL_CLAUDE = Config.GITHUB_MODEL_CLAUDE
BACKEND_URL = Config.BACKEND_URL
DATA_DIR = Config.DATA_DIR
MODELS_DIR = Config.MODELS_DIR
EXPERIENCES_FILE = Config.EXPERIENCES_FILE
MODEL_PATH = Config.MODEL_PATH

# Telegram Compatibilidad
TELEGRAM_API_ID = Config.TELEGRAM_API_ID
TELEGRAM_API_HASH = Config.TELEGRAM_API_HASH
TELEGRAM_PHONE = Config.TELEGRAM_PHONE
TELEGRAM_SESSION_NAME = Config.TELEGRAM_SESSION_NAME
TELEGRAM_CHATS = Config.TELEGRAM_CHATS

# Alias de compatibilidad (definidos por archivos que usan nombres diferentes)
EX_EMAIL = Config.EXNOVA_EMAIL
EX_PASSWORD = Config.EXNOVA_PASSWORD

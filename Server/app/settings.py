from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    
    SECRET_KEY: str
    HMAC_SECRET_KEY: str
    
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    COMMAND_REPLAY_WINDOW_SECONDS: int = 30
    
    BROKER_HOST: str = "localhost"
    BROKER_PORT: int = 8883

    MQTT_USERNAME: str
    MQTT_PASSWORD: str

    MQTT_CA_CERT: str

    PENDING_TIMEOUT_SECONDS: int = 50
    SENT_TIMEOUT_SECONDS: int = 50
        
    class Config:
        env_file = ".env"

settings = Settings()
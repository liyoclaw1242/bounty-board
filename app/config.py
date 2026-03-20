import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db: str = os.path.expanduser("~/.bounty/bounty.db")
    log: str = os.path.expanduser("~/.bounty/agent.log")
    repos_base_dir: str = os.path.expanduser("~/.bounty/repos")
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_prefix": "BOUNTY_"}


settings = Settings()

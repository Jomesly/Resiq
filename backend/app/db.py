import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class Database:
    def __init__(self, url: str, *, schema: str | None = None):
        if not url.startswith("postgresql"):
            raise ValueError("Resiq requires PostgreSQL for its job queue.")
        options = {"connect_timeout": 5}
        if schema:
            if not re.fullmatch(r"resiq_test_[a-f0-9]{32}", schema):
                raise ValueError("Only isolated test schemas may override search_path.")
            options["options"] = f"-csearch_path={schema}"
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=15,
            connect_args=options,
        )
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def dispose(self):
        self.engine.dispose()

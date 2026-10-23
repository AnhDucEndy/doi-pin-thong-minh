from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import sessionmaker


class Database:
    def __init__(self, settings):
        self.engine = create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True,
                                    connect_args={'options': f'-csearch_path={settings.schema},public -cstatement_timeout=15000 -clock_timeout=5000', 'connect_timeout': 5})
        self.metadata = MetaData()
        self.metadata.reflect(self.engine)
        self.tables = self.metadata.tables
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def table(self, name):
        return self.tables[name]


def advisory_lock(session, key):
    # Transaction-scoped, shared by all API processes; no in-memory rate/idempotency locks.
    session.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key': key})

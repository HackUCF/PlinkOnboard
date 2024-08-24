import logging
from uuid import UUID

# Create the database
from alembic import script
from alembic.runtime import migration
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from sqlalchemy.orm import selectinload
from app.models.user import UserModel, DiscordModel

from app.util.settings import Settings

DATABASE_URL = Settings().database.url
logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    # echo=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

if "sqlite:///:memory:" in DATABASE_URL:
    SQLModel.metadata.create_all(engine)
    logger.info("Tables created in SQLite in-memory database.")


def init_db():
    SQLModel.metadata.create_all(engine)
    return


def get_session():
    with Session(engine) as session:
        yield session


def check_current_head(alembic_cfg, connectable):
    # type: (config.Config, engine.Engine) -> bool
    # cfg = config.Config("../alembic.ini")
    directory = script.ScriptDirectory.from_config(alembic_cfg)
    with connectable.begin() as connection:
        context = migration.MigrationContext.configure(connection)
        return set(context.get_current_heads()) == set(directory.get_heads())

def get_user(session, user_id: UUID, use_selectinload: bool = False):
    query = session.query(UserModel).filter(UserModel.id == user_id)
    if selectinload:
        query = query.options(selectinload(UserModel.discord))
    return query.one_or_none()

def get_user_discord(session, discord_id, use_selectinload: bool = False):
    query = session.query(UserModel).filter(UserModel.discord_id == discord_id)
    if selectinload:
        query = query.options(selectinload(UserModel.discord))
    return query.one_or_none()

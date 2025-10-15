import os
from ..extensions import db


class GlobalItemAlias(db.Model):
    __tablename__ = 'global_item_alias'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    global_item_id = db.Column(db.Integer, db.ForeignKey('global_item.id', ondelete='CASCADE'), nullable=False)
    alias = db.Column(db.Text, nullable=False)

    def _is_postgres_url(url: str) -> bool:
        if not url:
            return False
        url = url.lower()
        return (
            url.startswith("postgres://")
            or url.startswith("postgresql://")
            or url.startswith("postgresql+psycopg2://")
        )

    _IS_PG = _is_postgres_url(os.environ.get("DATABASE_URL", ""))

    __table_args__ = tuple([
        db.Index('ix_global_item_alias_alias', 'alias'),
        db.Index('ix_global_item_alias_global_item_id', 'global_item_id'),
        *([db.Index('ix_global_item_alias_tsv', db.text("to_tsvector('simple', alias)"), postgresql_using='gin')] if _IS_PG else []),
    ])

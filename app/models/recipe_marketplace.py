import sqlalchemy as sa

from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
from .mixins import TimestampMixin


class RecipeProductGroup(db.Model, TimestampMixin):
    __tablename__ = 'recipe_product_group'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(64), nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=sa.text("true"))

    def __repr__(self) -> str:
        return f"<RecipeProductGroup {self.slug}>"


class RecipeModerationEvent(db.Model):
    __tablename__ = 'recipe_moderation_event'

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    moderated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(64), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    violation_delta = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)

    organization = db.relationship('Organization')
    moderator = db.relationship('User', foreign_keys=[moderated_by])

    __table_args__ = (
        db.Index('ix_recipe_moderation_recipe_id', 'recipe_id'),
        db.Index('ix_recipe_moderation_org_id', 'organization_id'),
    )

    def __repr__(self) -> str:
        return f"<RecipeModerationEvent recipe={self.recipe_id} action={self.action}>"

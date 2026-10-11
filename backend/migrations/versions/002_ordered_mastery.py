"""Do not replace newer mastery with a delayed assessment."""
from alembic import op
revision = '002_ordered_mastery'
down_revision = '001_v23'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('''CREATE OR REPLACE FUNCTION prepcrew.apply_assessment() RETURNS trigger LANGUAGE plpgsql
    SET search_path = prepcrew, public AS $$
    BEGIN
      INSERT INTO user_skills(user_id,skill_id,score,is_estimate,last_assessed_at)
      VALUES(NEW.user_id,NEW.skill_id,NEW.score,NEW.is_estimate,NEW.ts)
      ON CONFLICT(user_id,skill_id) DO UPDATE SET
        trend=NEW.score-COALESCE(user_skills.score,NEW.score), score=NEW.score,
        is_estimate=NEW.is_estimate,last_assessed_at=NEW.ts
      WHERE user_skills.last_assessed_at IS NULL OR NEW.ts >= user_skills.last_assessed_at;
      RETURN NEW;
    END $$''')

def downgrade():
    raise RuntimeError('Use a reviewed forward migration.')

"""add whatsapp webhook recovery lease fields

Revision ID: b1e9d4c7f0a2
Revises: efa066dfdf30
Create Date: 2026-07-22 00:00:00.000000

Etapa 1D — reprocesamiento seguro y retención de payloads.

Aditiva y NO destructiva sobre `whatsapp_webhook_events`: agrega tres columnas de
lease/reintento y dos índices parciales de PostgreSQL. No toca datos existentes, no
crea NOT NULL sin default, no toca tablas comerciales ni las otras tablas whatsapp_*.

Columnas:
  - processing_started_at : lease persistente; permite detectar `processing` atascados.
  - next_retry_at         : elegibilidad y backoff; evita reintentar poison pills en
                            cada corrida.
  - locked_by             : trazabilidad del worker que reclamó (NO sustituye el lock
                            de PostgreSQL; es solo informativo).

Índices parciales (PostgreSQL): acotan el costo a las filas realmente relevantes.
  - lease atascado    : WHERE processing_status = 'processing', por processing_started_at.
  - reintento elegible: WHERE processing_status IN ('failed','pending'), por
                        (next_retry_at, received_at).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1e9d4c7f0a2'
down_revision: Union[str, None] = 'efa066dfdf30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "whatsapp_webhook_events"
IX_LEASE = "ix_whatsapp_webhook_events_processing_lease"
IX_RETRY = "ix_whatsapp_webhook_events_retry_eligible"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABLE, sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABLE, sa.Column("locked_by", sa.String(length=64), nullable=True))

    op.create_index(
        IX_LEASE, TABLE, ["processing_started_at"], unique=False,
        postgresql_where=sa.text("processing_status = 'processing'"),
    )
    op.create_index(
        IX_RETRY, TABLE, ["next_retry_at", "received_at"], unique=False,
        postgresql_where=sa.text("processing_status IN ('failed', 'pending')"),
    )


def downgrade() -> None:
    op.drop_index(IX_RETRY, table_name=TABLE)
    op.drop_index(IX_LEASE, table_name=TABLE)
    op.drop_column(TABLE, "locked_by")
    op.drop_column(TABLE, "next_retry_at")
    op.drop_column(TABLE, "processing_started_at")

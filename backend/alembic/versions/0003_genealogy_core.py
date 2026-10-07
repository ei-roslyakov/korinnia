"""Genealogy core: places, persons, names, events, participants, relationships.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07 06:51:29.715153+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column(
            "gender",
            sa.Enum(
                "male",
                "female",
                "other",
                "unknown",
                name="gender",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("is_living", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("primary_photo_id", sa.Uuid(), nullable=True),
        sa.Column("short_summary", sa.String(length=500), nullable=True),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("occupation", sa.Text(), nullable=True),
        sa.Column("education", sa.Text(), nullable=True),
        sa.Column("religion", sa.String(length=200), nullable=True),
        sa.Column("nationality", sa.String(length=200), nullable=True),
        sa.Column("notes_for_descendants", sa.Text(), nullable=True),
        sa.Column(
            "research_status",
            sa.Enum(
                "complete",
                "partial",
                "unknown",
                name="research_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_batch_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_persons_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"], ["trees.id"], name=op.f("fk_persons_tree_id_trees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_persons_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_persons")),
    )
    op.create_index(op.f("ix_persons_deleted_at"), "persons", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_persons_deleted_batch_id"), "persons", ["deleted_batch_id"], unique=False
    )
    op.create_index(op.f("ix_persons_tree_id"), "persons", ["tree_id"], unique=False)
    op.create_table(
        "places",
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column(
            "historical_names",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=200), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_batch_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name=op.f("ck_places_latitude_range")),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_places_longitude_range")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_places_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"], ["trees.id"], name=op.f("fk_places_tree_id_trees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_places_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_places")),
    )
    op.create_index(op.f("ix_places_deleted_at"), "places", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_places_deleted_batch_id"), "places", ["deleted_batch_id"], unique=False
    )
    op.create_index(
        "ix_places_search_text_trgm",
        "places",
        ["search_text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.create_index(op.f("ix_places_tree_id"), "places", ["tree_id"], unique=False)
    op.create_table(
        "events",
        sa.Column(
            "type",
            sa.Enum(
                "birth",
                "baptism",
                "death",
                "burial",
                "marriage",
                "divorce",
                "education",
                "graduation",
                "military_service",
                "occupation",
                "residence",
                "emigration",
                "immigration",
                "award",
                "illness",
                "custom",
                name="event_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("date_year", sa.Integer(), nullable=True),
        sa.Column("date_month", sa.SmallInteger(), nullable=True),
        sa.Column("date_day", sa.SmallInteger(), nullable=True),
        sa.Column(
            "date_precision",
            sa.Enum(
                "exact",
                "month",
                "year",
                "approx",
                "before",
                "after",
                "between",
                "unknown",
                name="date_precision",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("date_end_year", sa.Integer(), nullable=True),
        sa.Column("date_end_month", sa.SmallInteger(), nullable=True),
        sa.Column("date_end_day", sa.SmallInteger(), nullable=True),
        sa.Column("date_phrase", sa.String(length=200), nullable=True),
        sa.Column("date_sort", sa.Date(), nullable=True),
        sa.Column("place_id", sa.Uuid(), nullable=True),
        sa.Column("cemetery_name", sa.String(length=300), nullable=True),
        sa.Column("burial_plot", sa.String(length=200), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_batch_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name=op.f("ck_events_latitude_range")),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_events_longitude_range")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_events_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["place_id"], ["places.id"], name=op.f("fk_events_place_id_places"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"], ["trees.id"], name=op.f("fk_events_tree_id_trees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_events_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index(op.f("ix_events_date_sort"), "events", ["date_sort"], unique=False)
    op.create_index(op.f("ix_events_deleted_at"), "events", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_events_deleted_batch_id"), "events", ["deleted_batch_id"], unique=False
    )
    op.create_index(op.f("ix_events_place_id"), "events", ["place_id"], unique=False)
    op.create_index(op.f("ix_events_tree_id"), "events", ["tree_id"], unique=False)
    op.create_index(op.f("ix_events_type"), "events", ["type"], unique=False)
    op.create_table(
        "parent_child",
        sa.Column("parent_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "biological",
                "adoptive",
                "step",
                "foster",
                "unknown",
                name="parent_child_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_batch_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("parent_id <> child_id", name=op.f("ck_parent_child_not_self")),
        sa.ForeignKeyConstraint(
            ["child_id"],
            ["persons.id"],
            name=op.f("fk_parent_child_child_id_persons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_parent_child_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["persons.id"],
            name=op.f("fk_parent_child_parent_id_persons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["trees.id"],
            name=op.f("fk_parent_child_tree_id_trees"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_parent_child_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parent_child")),
    )
    op.create_index(op.f("ix_parent_child_child_id"), "parent_child", ["child_id"], unique=False)
    op.create_index(
        op.f("ix_parent_child_deleted_at"), "parent_child", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_parent_child_deleted_batch_id"), "parent_child", ["deleted_batch_id"], unique=False
    )
    op.create_index(op.f("ix_parent_child_parent_id"), "parent_child", ["parent_id"], unique=False)
    op.create_index(op.f("ix_parent_child_tree_id"), "parent_child", ["tree_id"], unique=False)
    op.create_index(
        "uq_parent_child_pair_live",
        "parent_child",
        ["parent_id", "child_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "partnerships",
        sa.Column("person_a_id", sa.Uuid(), nullable=False),
        sa.Column("person_b_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "marriage",
                "civil_union",
                "partnership",
                name="partnership_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("start_month", sa.SmallInteger(), nullable=True),
        sa.Column("start_day", sa.SmallInteger(), nullable=True),
        sa.Column(
            "start_precision",
            sa.Enum(
                "exact",
                "month",
                "year",
                "approx",
                "before",
                "after",
                "between",
                "unknown",
                name="start_precision",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("start_end_year", sa.Integer(), nullable=True),
        sa.Column("start_end_month", sa.SmallInteger(), nullable=True),
        sa.Column("start_end_day", sa.SmallInteger(), nullable=True),
        sa.Column("start_phrase", sa.String(length=200), nullable=True),
        sa.Column("start_sort", sa.Date(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("end_month", sa.SmallInteger(), nullable=True),
        sa.Column("end_day", sa.SmallInteger(), nullable=True),
        sa.Column(
            "end_precision",
            sa.Enum(
                "exact",
                "month",
                "year",
                "approx",
                "before",
                "after",
                "between",
                "unknown",
                name="end_precision",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("end_end_year", sa.Integer(), nullable=True),
        sa.Column("end_end_month", sa.SmallInteger(), nullable=True),
        sa.Column("end_end_day", sa.SmallInteger(), nullable=True),
        sa.Column("end_phrase", sa.String(length=200), nullable=True),
        sa.Column("end_sort", sa.Date(), nullable=True),
        sa.Column(
            "end_reason",
            sa.Enum(
                "divorce",
                "death",
                "separation",
                "other",
                name="end_reason",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("place_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_batch_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("person_a_id <> person_b_id", name=op.f("ck_partnerships_not_self")),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_partnerships_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["person_a_id"],
            ["persons.id"],
            name=op.f("fk_partnerships_person_a_id_persons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_b_id"],
            ["persons.id"],
            name=op.f("fk_partnerships_person_b_id_persons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["places.id"],
            name=op.f("fk_partnerships_place_id_places"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["trees.id"],
            name=op.f("fk_partnerships_tree_id_trees"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_partnerships_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partnerships")),
    )
    op.create_index(
        op.f("ix_partnerships_deleted_at"), "partnerships", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_partnerships_deleted_batch_id"), "partnerships", ["deleted_batch_id"], unique=False
    )
    op.create_index(op.f("ix_partnerships_end_sort"), "partnerships", ["end_sort"], unique=False)
    op.create_index(
        op.f("ix_partnerships_person_a_id"), "partnerships", ["person_a_id"], unique=False
    )
    op.create_index(
        op.f("ix_partnerships_person_b_id"), "partnerships", ["person_b_id"], unique=False
    )
    op.create_index(op.f("ix_partnerships_place_id"), "partnerships", ["place_id"], unique=False)
    op.create_index(
        op.f("ix_partnerships_start_sort"), "partnerships", ["start_sort"], unique=False
    )
    op.create_index(op.f("ix_partnerships_tree_id"), "partnerships", ["tree_id"], unique=False)
    op.create_table(
        "person_names",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "birth",
                "married",
                "nickname",
                "alias",
                "religious",
                "other",
                name="name_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("first_name", sa.String(length=200), nullable=True),
        sa.Column("middle_name", sa.String(length=200), nullable=True),
        sa.Column("patronymic", sa.String(length=200), nullable=True),
        sa.Column("last_name", sa.String(length=200), nullable=True),
        sa.Column("maiden_name", sa.String(length=200), nullable=True),
        sa.Column(
            "script",
            sa.Enum(
                "cyrillic",
                "latin",
                "other",
                name="script",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_person_names_person_id_persons"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_person_names")),
    )
    op.create_index(op.f("ix_person_names_person_id"), "person_names", ["person_id"], unique=False)
    op.create_index(
        "ix_person_names_search_text_trgm",
        "person_names",
        ["search_text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.create_table(
        "event_participants",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "principal",
                "spouse",
                "witness",
                "godparent",
                "officiant",
                "other",
                name="participant_role",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_participants_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_event_participants_person_id_persons"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_participants")),
        sa.UniqueConstraint(
            "event_id", "person_id", name=op.f("uq_event_participants_event_id_person_id")
        ),
    )
    op.create_index(
        op.f("ix_event_participants_event_id"), "event_participants", ["event_id"], unique=False
    )
    op.create_index(
        op.f("ix_event_participants_person_id"), "event_participants", ["person_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_event_participants_person_id"), table_name="event_participants")
    op.drop_index(op.f("ix_event_participants_event_id"), table_name="event_participants")
    op.drop_table("event_participants")
    op.drop_index(
        "ix_person_names_search_text_trgm",
        table_name="person_names",
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.drop_index(op.f("ix_person_names_person_id"), table_name="person_names")
    op.drop_table("person_names")
    op.drop_index(op.f("ix_partnerships_tree_id"), table_name="partnerships")
    op.drop_index(op.f("ix_partnerships_start_sort"), table_name="partnerships")
    op.drop_index(op.f("ix_partnerships_place_id"), table_name="partnerships")
    op.drop_index(op.f("ix_partnerships_person_b_id"), table_name="partnerships")
    op.drop_index(op.f("ix_partnerships_person_a_id"), table_name="partnerships")
    op.drop_index(op.f("ix_partnerships_end_sort"), table_name="partnerships")
    op.drop_index(op.f("ix_partnerships_deleted_batch_id"), table_name="partnerships")
    op.drop_index(op.f("ix_partnerships_deleted_at"), table_name="partnerships")
    op.drop_table("partnerships")
    op.drop_index(
        "uq_parent_child_pair_live",
        table_name="parent_child",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(op.f("ix_parent_child_tree_id"), table_name="parent_child")
    op.drop_index(op.f("ix_parent_child_parent_id"), table_name="parent_child")
    op.drop_index(op.f("ix_parent_child_deleted_batch_id"), table_name="parent_child")
    op.drop_index(op.f("ix_parent_child_deleted_at"), table_name="parent_child")
    op.drop_index(op.f("ix_parent_child_child_id"), table_name="parent_child")
    op.drop_table("parent_child")
    op.drop_index(op.f("ix_events_type"), table_name="events")
    op.drop_index(op.f("ix_events_tree_id"), table_name="events")
    op.drop_index(op.f("ix_events_place_id"), table_name="events")
    op.drop_index(op.f("ix_events_deleted_batch_id"), table_name="events")
    op.drop_index(op.f("ix_events_deleted_at"), table_name="events")
    op.drop_index(op.f("ix_events_date_sort"), table_name="events")
    op.drop_table("events")
    op.drop_index(op.f("ix_places_tree_id"), table_name="places")
    op.drop_index(
        "ix_places_search_text_trgm",
        table_name="places",
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.drop_index(op.f("ix_places_deleted_batch_id"), table_name="places")
    op.drop_index(op.f("ix_places_deleted_at"), table_name="places")
    op.drop_table("places")
    op.drop_index(op.f("ix_persons_tree_id"), table_name="persons")
    op.drop_index(op.f("ix_persons_deleted_batch_id"), table_name="persons")
    op.drop_index(op.f("ix_persons_deleted_at"), table_name="persons")
    op.drop_table("persons")

"""Sources, citations, stories, edit suggestions, comments, open questions.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-07 09:06:24.360038+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column(
            "entity_type",
            sa.Enum(
                "person",
                "story",
                "media",
                name="comment_target",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
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
            ["author_id"],
            ["users.id"],
            name=op.f("fk_comments_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"], ["trees.id"], name=op.f("fk_comments_tree_id_trees"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )
    op.create_index(op.f("ix_comments_author_id"), "comments", ["author_id"], unique=False)
    op.create_index("ix_comments_target", "comments", ["entity_type", "entity_id"], unique=False)
    op.create_index(op.f("ix_comments_tree_id"), "comments", ["tree_id"], unique=False)
    op.create_table(
        "edit_suggestions",
        sa.Column(
            "entity_type",
            sa.Enum(
                "person",
                "event",
                name="suggestion_target",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("patch", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                name="suggestion_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
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
            name=op.f("fk_edit_suggestions_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name=op.f("fk_edit_suggestions_reviewed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["trees.id"],
            name=op.f("fk_edit_suggestions_tree_id_trees"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edit_suggestions")),
    )
    op.create_index(
        op.f("ix_edit_suggestions_created_by_id"),
        "edit_suggestions",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_edit_suggestions_status"), "edit_suggestions", ["status"], unique=False
    )
    op.create_index(
        "ix_edit_suggestions_target", "edit_suggestions", ["entity_type", "entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_edit_suggestions_tree_id"), "edit_suggestions", ["tree_id"], unique=False
    )
    op.create_table(
        "sources",
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "civil_record",
                "church_record",
                "archive_document",
                "census",
                "newspaper",
                "letter",
                "oral_history",
                "book",
                "website",
                "other",
                name="source_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("author", sa.String(length=300), nullable=True),
        sa.Column("archive_name", sa.String(length=300), nullable=True),
        sa.Column("reference_number", sa.String(length=300), nullable=True),
        sa.Column("url", sa.String(length=2000), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_sources_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"], ["trees.id"], name=op.f("fk_sources_tree_id_trees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_sources_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
    )
    op.create_index(op.f("ix_sources_deleted_at"), "sources", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_sources_deleted_batch_id"), "sources", ["deleted_batch_id"], unique=False
    )
    op.create_index(
        "ix_sources_search_text_trgm",
        "sources",
        ["search_text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.create_index(op.f("ix_sources_tree_id"), "sources", ["tree_id"], unique=False)
    op.create_table(
        "stories",
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("narrator", sa.String(length=300), nullable=True),
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
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "pending_review",
                "published",
                name="story_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
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
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_stories_author_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_stories_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"], ["trees.id"], name=op.f("fk_stories_tree_id_trees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_stories_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stories")),
    )
    op.create_index(op.f("ix_stories_author_user_id"), "stories", ["author_user_id"], unique=False)
    op.create_index(op.f("ix_stories_date_sort"), "stories", ["date_sort"], unique=False)
    op.create_index(op.f("ix_stories_deleted_at"), "stories", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_stories_deleted_batch_id"), "stories", ["deleted_batch_id"], unique=False
    )
    op.create_index(op.f("ix_stories_status"), "stories", ["status"], unique=False)
    op.create_index(op.f("ix_stories_tree_id"), "stories", ["tree_id"], unique=False)
    op.create_table(
        "citations",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum(
                "person",
                "person_name",
                "event",
                "parent_child",
                "partnership",
                "media",
                name="cited_entity",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(length=100), nullable=True),
        sa.Column("page", sa.String(length=300), nullable=True),
        sa.Column(
            "quality",
            sa.Enum(
                "primary",
                "secondary",
                "family_tradition",
                "unverified",
                name="citation_quality",
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
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_citations_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_citations_source_id_sources"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"], ["trees.id"], name=op.f("fk_citations_tree_id_trees"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_citations_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_citations")),
    )
    op.create_index(op.f("ix_citations_deleted_at"), "citations", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_citations_deleted_batch_id"), "citations", ["deleted_batch_id"], unique=False
    )
    op.create_index("ix_citations_entity", "citations", ["entity_type", "entity_id"], unique=False)
    op.create_index(op.f("ix_citations_source_id"), "citations", ["source_id"], unique=False)
    op.create_index(op.f("ix_citations_tree_id"), "citations", ["tree_id"], unique=False)
    op.create_table(
        "open_questions",
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "resolved",
                name="question_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tree_id", sa.Uuid(), nullable=False),
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
            name=op.f("fk_open_questions_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_open_questions_person_id_persons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tree_id"],
            ["trees.id"],
            name=op.f("fk_open_questions_tree_id_trees"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_open_questions")),
    )
    op.create_index(
        op.f("ix_open_questions_person_id"), "open_questions", ["person_id"], unique=False
    )
    op.create_index(op.f("ix_open_questions_status"), "open_questions", ["status"], unique=False)
    op.create_index(op.f("ix_open_questions_tree_id"), "open_questions", ["tree_id"], unique=False)
    op.create_table(
        "story_persons",
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["persons.id"],
            name=op.f("fk_story_persons_person_id_persons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_story_persons_story_id_stories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("story_id", "person_id", name=op.f("pk_story_persons")),
    )
    op.create_index(
        op.f("ix_story_persons_person_id"), "story_persons", ["person_id"], unique=False
    )
    op.create_table(
        "source_media",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media_files.id"],
            name=op.f("fk_source_media_media_id_media_files"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_source_media_source_id_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_id", "media_id", name=op.f("pk_source_media")),
    )
    op.create_table(
        "story_media",
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media_files.id"],
            name=op.f("fk_story_media_media_id_media_files"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            ["stories.id"],
            name=op.f("fk_story_media_story_id_stories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("story_id", "media_id", name=op.f("pk_story_media")),
    )


def downgrade() -> None:
    op.drop_table("story_media")
    op.drop_table("source_media")
    op.drop_index(op.f("ix_story_persons_person_id"), table_name="story_persons")
    op.drop_table("story_persons")
    op.drop_index(op.f("ix_open_questions_tree_id"), table_name="open_questions")
    op.drop_index(op.f("ix_open_questions_status"), table_name="open_questions")
    op.drop_index(op.f("ix_open_questions_person_id"), table_name="open_questions")
    op.drop_table("open_questions")
    op.drop_index(op.f("ix_citations_tree_id"), table_name="citations")
    op.drop_index(op.f("ix_citations_source_id"), table_name="citations")
    op.drop_index("ix_citations_entity", table_name="citations")
    op.drop_index(op.f("ix_citations_deleted_batch_id"), table_name="citations")
    op.drop_index(op.f("ix_citations_deleted_at"), table_name="citations")
    op.drop_table("citations")
    op.drop_index(op.f("ix_stories_tree_id"), table_name="stories")
    op.drop_index(op.f("ix_stories_status"), table_name="stories")
    op.drop_index(op.f("ix_stories_deleted_batch_id"), table_name="stories")
    op.drop_index(op.f("ix_stories_deleted_at"), table_name="stories")
    op.drop_index(op.f("ix_stories_date_sort"), table_name="stories")
    op.drop_index(op.f("ix_stories_author_user_id"), table_name="stories")
    op.drop_table("stories")
    op.drop_index(op.f("ix_sources_tree_id"), table_name="sources")
    op.drop_index(
        "ix_sources_search_text_trgm",
        table_name="sources",
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.drop_index(op.f("ix_sources_deleted_batch_id"), table_name="sources")
    op.drop_index(op.f("ix_sources_deleted_at"), table_name="sources")
    op.drop_table("sources")
    op.drop_index(op.f("ix_edit_suggestions_tree_id"), table_name="edit_suggestions")
    op.drop_index("ix_edit_suggestions_target", table_name="edit_suggestions")
    op.drop_index(op.f("ix_edit_suggestions_status"), table_name="edit_suggestions")
    op.drop_index(op.f("ix_edit_suggestions_created_by_id"), table_name="edit_suggestions")
    op.drop_table("edit_suggestions")
    op.drop_index(op.f("ix_comments_tree_id"), table_name="comments")
    op.drop_index("ix_comments_target", table_name="comments")
    op.drop_index(op.f("ix_comments_author_id"), table_name="comments")
    op.drop_table("comments")

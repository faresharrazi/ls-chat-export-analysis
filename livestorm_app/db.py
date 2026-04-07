import hashlib
import json
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from psycopg import connect
from psycopg.rows import dict_row


DATABASE_URL_ENV_VARS = ("DATABASE_URL", "POSTGRES_URL", "RENDER_POSTGRES_URL")


def get_database_url() -> str:
    for env_var in DATABASE_URL_ENV_VARS:
        value = str(os.getenv(env_var, "") or "").strip()
        if value:
            return value
    return ""


def database_enabled() -> bool:
    return bool(get_database_url())


def build_account_key_hash(api_key: str) -> str:
    return hashlib.sha256(str(api_key or "").strip().encode("utf-8")).hexdigest()


@contextmanager
def get_db_connection() -> Iterator[Any]:
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("Database is not configured.")
    with connect(database_url, row_factory=dict_row) as connection:
        yield connection


def ensure_database_schema() -> None:
    if not database_enabled():
        return

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_cache (
                    account_key_hash TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    session_payload JSONB,
                    chat_payload JSONB,
                    questions_payload JSONB,
                    transcript_payload JSONB,
                    analysis_md TEXT,
                    analysis_bundle JSONB,
                    deep_analysis_md TEXT,
                    deep_analysis_bundle JSONB,
                    content_repurpose_bundle JSONB,
                    smart_recap_bundle JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (account_key_hash, session_id)
                )
                """
            )
            cursor.execute(
                """
                ALTER TABLE session_cache
                ADD COLUMN IF NOT EXISTS session_payload JSONB
                """
            )
            cursor.execute(
                """
                ALTER TABLE session_cache
                ADD COLUMN IF NOT EXISTS analysis_bundle JSONB
                """
            )
            cursor.execute(
                """
                ALTER TABLE session_cache
                ADD COLUMN IF NOT EXISTS deep_analysis_bundle JSONB
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_cache_account_hash
                ON session_cache (account_key_hash)
                """
            )
            cursor.execute(
                """
                DELETE FROM session_cache
                WHERE ctid IN (
                    SELECT ctid
                    FROM (
                        SELECT
                            ctid,
                            ROW_NUMBER() OVER (
                                PARTITION BY session_id
                                ORDER BY updated_at DESC, created_at DESC
                            ) AS row_rank
                        FROM session_cache
                    ) ranked_rows
                    WHERE row_rank > 1
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_cache_session_id
                ON session_cache (session_id)
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_session_cache_session_id_unique
                ON session_cache (session_id)
                """
            )
        connection.commit()


def fetch_cached_session(api_key: str, session_id: str) -> Optional[Dict[str, Any]]:
    if not database_enabled() or not str(session_id or "").strip():
        return None

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    account_key_hash,
                    session_id,
                    session_payload,
                    chat_payload,
                    questions_payload,
                    transcript_payload,
                    analysis_md,
                    analysis_bundle,
                    deep_analysis_md,
                    deep_analysis_bundle,
                    content_repurpose_bundle,
                    smart_recap_bundle,
                    created_at,
                    updated_at
                FROM session_cache
                WHERE session_id = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (str(session_id).strip(),),
            )
            row = cursor.fetchone()
    return dict(row) if isinstance(row, dict) else None


def upsert_cached_session(api_key: str, session_id: str, **fields: Any) -> None:
    if not database_enabled() or not str(api_key or "").strip() or not str(session_id or "").strip():
        return

    allowed_fields = {
        "session_payload",
        "chat_payload",
        "questions_payload",
        "transcript_payload",
        "analysis_md",
        "analysis_bundle",
        "deep_analysis_md",
        "deep_analysis_bundle",
        "content_repurpose_bundle",
        "smart_recap_bundle",
    }
    persisted_fields = {key: value for key, value in fields.items() if key in allowed_fields}
    if not persisted_fields:
        return

    session_id_value = str(session_id).strip()
    account_key_hash = build_account_key_hash(api_key)
    columns = ["account_key_hash", "session_id", *persisted_fields.keys()]
    placeholders = ["%s", "%s"]
    insert_values = [account_key_hash, session_id_value]
    update_clauses = ["account_key_hash = EXCLUDED.account_key_hash"]

    for key, value in persisted_fields.items():
        if isinstance(value, (dict, list)):
            insert_values.append(json.dumps(value, ensure_ascii=False))
            placeholders.append("%s::jsonb")
        else:
            insert_values.append(value)
            placeholders.append("%s")
        update_clauses.append(f"{key} = EXCLUDED.{key}")

    update_clauses.append("updated_at = NOW()")

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO session_cache ({", ".join(columns)})
                VALUES ({", ".join(placeholders)})
                ON CONFLICT (session_id)
                DO UPDATE SET {", ".join(update_clauses)}
                """,
                insert_values,
            )
        connection.commit()

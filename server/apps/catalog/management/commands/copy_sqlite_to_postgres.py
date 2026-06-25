import sqlite3
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.catalog.search import product_search_text

DEFAULT_TABLES = [
    "catalog_marketplace",
    "catalog_seller",
    "catalog_category",
    "catalog_product",
    "crawling_crawlrun",
    "crawling_crawlrunseenproduct",
    "crawling_crawlevent",
    "catalog_productsnapshot",
]
SEARCH_TERM_TABLE = "catalog_productsearchterm"


class Command(BaseCommand):
    help = "Copy existing SQLite catalog data into the configured PostgreSQL database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="Path to the source SQLite database.",
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Truncate target catalog/crawling tables before copying.",
        )
        parser.add_argument(
            "--include-search-terms",
            action="store_true",
            help="Also copy catalog_productsearchterm. Usually rebuild it instead.",
        )
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Default DATABASE_URL must point to PostgreSQL.")

        sqlite_path = Path(options["sqlite_path"]).expanduser().resolve()
        if not sqlite_path.exists():
            raise CommandError(f"SQLite database does not exist: {sqlite_path}")

        tables = [*DEFAULT_TABLES]
        if options["include_search_terms"]:
            tables.append(SEARCH_TERM_TABLE)

        self.stdout.write(f"Copying SQLite data from {sqlite_path}")
        with sqlite3.connect(sqlite_path) as source:
            source.row_factory = sqlite3.Row
            self._copy_tables(
                source=source,
                tables=tables,
                truncate=options["truncate"],
                batch_size=options["batch_size"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                "SQLite data copied. Run rebuild_product_search_index unless "
                "--include-search-terms was used."
            )
        )

    @transaction.atomic
    def _copy_tables(
        self,
        *,
        source: sqlite3.Connection,
        tables: list[str],
        truncate: bool,
        batch_size: int,
    ) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            if truncate:
                quoted_tables = ", ".join(
                    connection.ops.quote_name(table) for table in reversed(tables)
                )
                cursor.execute(f"TRUNCATE {quoted_tables} RESTART IDENTITY CASCADE")

        for table in tables:
            copied = self._copy_table(source=source, table=table, batch_size=batch_size)
            self.stdout.write(f"Copied {copied} rows into {table}.")
            self._reset_sequence(table)

    def _copy_table(
        self,
        *,
        source: sqlite3.Connection,
        table: str,
        batch_size: int,
    ) -> int:
        source_columns = _sqlite_columns(source, table)
        target_columns = _postgres_columns(table)
        copy_columns = [column for column in target_columns if column in source_columns]
        extra_columns = [column for column in target_columns if column not in source_columns]
        if table == "catalog_product" and "search_text" in extra_columns:
            copy_columns.append("search_text")

        if not copy_columns:
            return 0

        select_columns = ", ".join(_quote_sqlite(column) for column in source_columns)
        source_cursor = source.execute(f"SELECT {select_columns} FROM {_quote_sqlite(table)}")
        quoted_columns = ", ".join(connection.ops.quote_name(column) for column in copy_columns)
        copy_sql = f"COPY {connection.ops.quote_name(table)} ({quoted_columns}) FROM STDIN"

        copied = 0
        batch: list[sqlite3.Row] = []
        connection.ensure_connection()
        raw_connection = connection.connection
        with raw_connection.cursor() as cursor:
            with cursor.copy(copy_sql) as copy:
                for row in source_cursor:
                    batch.append(row)
                    if len(batch) >= batch_size:
                        copied += self._write_rows(copy, table, copy_columns, batch)
                        batch.clear()
                if batch:
                    copied += self._write_rows(copy, table, copy_columns, batch)
        return copied

    def _write_rows(self, copy, table: str, columns: list[str], rows: list[sqlite3.Row]) -> int:
        for row in rows:
            copy.write_row([_row_value(table, row, column) for column in columns])
        return len(rows)

    def _reset_sequence(self, table: str) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
                  AND column_default LIKE 'nextval%%'
                """,
                [table],
            )
            row = cursor.fetchone()
            if not row:
                return
            column = row[0]
            quoted_table = connection.ops.quote_name(table)
            cursor.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(%s, %s),
                    COALESCE(MAX(id), 1),
                    MAX(id) IS NOT NULL
                )
                FROM {quoted_table}
                """,
                [table, column],
            )


def _sqlite_columns(source: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in source.execute(f"PRAGMA table_info({_quote_sqlite(table)})")]


def _postgres_columns(table: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            [table],
        )
        return [row[0] for row in cursor.fetchall()]


def _row_value(table: str, row: sqlite3.Row, column: str) -> Any:
    if table == "catalog_product" and column == "search_text" and (
        column not in row.keys() or not row[column]
    ):
        return product_search_text(
            title=row["title"],
            description=row["description"] if "description" in row.keys() else None,
            brand=row["brand"],
            category_path_text=row["category_path_text"],
            source_product_id=row["source_product_id"],
            specs=row["specs"] if "specs" in row.keys() else None,
        )
    return row[column]


def _quote_sqlite(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'

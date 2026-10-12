"""Read-only role/data verification for the isolated M6 rehearsal project."""

import json
import subprocess
from pathlib import Path


def main():
    compose = [
        "docker",
        "compose",
        "--env-file",
        ".env.production",
        "-f",
        "compose.production.yaml",
    ]
    # This acceptance helper must not run against an arbitrary production project.
    environment = dict(
        line.split("=", 1)
        for line in Path(".env.production").read_text().splitlines()
        if "=" in line
    )
    if environment.get("PRODUCTION_PROJECT") != "stockinsight-m6":
        raise ValueError("Only the isolated rehearsal project is supported")

    def query(database, statement):
        return json.loads(
            subprocess.check_output(
                [
                    *compose,
                    "exec",
                    "-T",
                    "db",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    database,
                    "-XAt",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    "BEGIN READ ONLY; " + statement + "; COMMIT",
                ],
                text=True,
            ).splitlines()[1]
        )

    tables = ("stocks", "daily_prices", "technical_indicators", "data_sync_jobs")
    statements = []
    for table in tables:
        statements.extend(
            [
                "'" + table + "'",
                "(SELECT json_build_object('rows',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(record, E'\\n' ORDER BY record),''),'UTF8')),'hex')) FROM (SELECT row_to_json(t)::text AS record FROM "
                + table
                + " t) s)",
            ]
        )
    sql = "SELECT json_build_object(" + ",".join(statements) + ")"
    original = query("stockinsight", sql)
    restored = query("stockinsight_capacity_restore", sql)
    assert original == restored, "Restored table contents differ"
    privileges = query(
        "stockinsight",
        "SELECT json_build_object('api_select',has_table_privilege('si_api','stocks','SELECT'),'api_insert',has_table_privilege('si_api','stocks','INSERT'),'worker_insert',has_table_privilege('si_worker','daily_prices','INSERT'),'worker_delete',has_table_privilege('si_worker','daily_prices','DELETE'),'backup_select',has_table_privilege('si_backup','stocks','SELECT'),'backup_update',has_table_privilege('si_backup','stocks','UPDATE'),'api_create',has_schema_privilege('si_api','public','CREATE'))",
    )
    assert privileges == {
        "api_select": True,
        "api_insert": False,
        "worker_insert": True,
        "worker_delete": False,
        "backup_select": True,
        "backup_update": False,
        "api_create": False,
    }
    size = query(
        "stockinsight",
        "SELECT json_build_object('database_bytes',pg_database_size(current_database()),'covered_symbols',(SELECT count(DISTINCT symbol) FROM daily_prices),'revision',(SELECT version_num FROM alembic_version))",
    )
    print(
        json.dumps(
            {
                "restored_content_matches": True,
                "tables": original,
                "privileges": privileges,
                **size,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

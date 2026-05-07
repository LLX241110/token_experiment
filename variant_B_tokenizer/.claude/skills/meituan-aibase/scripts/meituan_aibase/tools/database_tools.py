"""
DatabaseTools：AI Base 数据库操作（基于 PostgREST）
version: 0.1.0

AI Base 100% 兼容 Supabase/PostgreSQL 语法。
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from .base import BaseTools, to_json, read_only_check, handle_errors
from ..config import resolve_pg_roles

logger = logging.getLogger(__name__)


class DatabaseTools(BaseTools):

    async def _execute_sql_raw(self, query: str) -> List[dict]:
        if not query or not query.strip():
            raise ValueError("SQL 语句不能为空")
        client = await self._get_client()
        result = await client.call_api("/pg/query", method="POST", json_data={"query": query})
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            result = result["data"]
        if not isinstance(result, list):
            raise TypeError(f"SQL 执行结果类型异常：{type(result).__name__}，原始内容：{result}")
        return result

    async def execute_sql(self, query: str) -> str:
        """执行任意 SQL 语句"""
        try:
            rows = await self._execute_sql_raw(query)
            return to_json({"success": True, "rows": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"execute_sql 失败: {e}")
            return to_json({"success": False, "error": str(e)})

    async def list_tables(self, schemas: Optional[List[str]] = None) -> str:
        """列出指定 schema 下的所有表"""
        if schemas is None:
            schemas = ["public"]
        for schema in schemas:
            if not schema.replace("_", "").isalnum():
                return to_json({"success": False, "error": f"非法 schema 名称：{schema}"})
        schema_list = "', '".join(schemas)
        query = f"""
        SELECT
            schemaname AS schema,
            tablename  AS name
        FROM pg_tables
        WHERE schemaname IN ('{schema_list}')
        ORDER BY schemaname, tablename
        """
        try:
            rows = await self._execute_sql_raw(query)
            return to_json({"success": True, "tables": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"list_tables 失败: {e}")
            return to_json({"success": False, "error": str(e)})

    async def list_extensions(self) -> str:
        """列出已安装的 PostgreSQL 扩展"""
        query = """
        SELECT
            e.extname  AS name,
            n.nspname  AS schema,
            e.extversion AS version
        FROM pg_extension e
        JOIN pg_namespace n ON n.oid = e.extnamespace
        ORDER BY e.extname
        """
        try:
            rows = await self._execute_sql_raw(query)
            return to_json({"success": True, "extensions": rows})
        except Exception as e:
            logger.error(f"list_extensions 失败: {e}")
            return to_json({"success": False, "error": str(e)})

    async def list_migrations(self) -> str:
        """列出迁移记录（自动创建 schema_migrations 表）"""
        setup_sql = """
        CREATE SCHEMA IF NOT EXISTS supabase_migrations;
        CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
            version     text        PRIMARY KEY,
            name        text        NOT NULL,
            inserted_at timestamptz NOT NULL DEFAULT now()
        );
        """
        select_sql = """
        SELECT version, name, inserted_at
        FROM supabase_migrations.schema_migrations
        ORDER BY version DESC
        """
        try:
            # DDL 和 SELECT 分开执行，避免混合事务问题
            await self._execute_sql_raw(setup_sql)
            rows = await self._execute_sql_raw(select_sql)
            return to_json({"success": True, "migrations": rows, "count": len(rows)})
        except Exception as e:
            logger.error(f"list_migrations 失败: {e}")
            return to_json({"success": False, "error": str(e)})

    @read_only_check
    async def apply_migration(self, name: str, query: str) -> str:
        """执行带版本追踪的数据库迁移（分两步执行，避免 DDL+DML 混合事务问题）"""
        if not name or not name.strip():
            return to_json({"success": False, "error": "迁移名称（name）不能为空"})
        if not query or not query.strip():
            return to_json({"success": False, "error": "迁移 SQL 不能为空"})

        migration_name = name.strip().replace("'", "''")
        migration_version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")

        # 自动将标准角色名替换为带 branch uuid 后缀的实际角色名
        query = resolve_pg_roles(query)

        # 步骤 1：确保 migrations 追踪表存在（DDL，单独执行）
        setup_sql = """
        CREATE SCHEMA IF NOT EXISTS supabase_migrations;
        CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
            version     text        PRIMARY KEY,
            name        text        NOT NULL,
            inserted_at timestamptz NOT NULL DEFAULT now()
        );
        """
        # 步骤 2：执行用户迁移 SQL（DDL，单独执行）
        # 步骤 3：记录迁移版本（DML，单独执行）
        record_sql = f"""
        INSERT INTO supabase_migrations.schema_migrations (version, name)
        VALUES ('{migration_version}', '{migration_name}')
        ON CONFLICT (version) DO UPDATE SET name = EXCLUDED.name;
        """
        try:
            await self._execute_sql_raw(setup_sql)
            await self._execute_sql_raw(query)
            await self._execute_sql_raw(record_sql)
            return to_json({
                "success": True,
                "message": f"迁移 '{name}' 已成功执行",
                "version": migration_version,
                "name": name.strip(),
            })
        except Exception as e:
            logger.error(f"apply_migration 失败: {e}")
            return to_json({"success": False, "error": str(e)})

    async def generate_typescript_types(self, schemas: Optional[List[str]] = None) -> str:
        """根据数据库表结构生成 TypeScript 类型定义"""
        if schemas is None:
            schemas = ["public"]
        for schema in schemas:
            if not schema.replace("_", "").isalnum():
                return to_json({"success": False, "error": f"非法 schema 名称：{schema}"})

        schema_list = "', '".join(schemas)
        query = f"""
        SELECT
            table_schema,
            table_name,
            column_name,
            is_nullable,
            is_identity,
            data_type,
            udt_name,
            column_default
        FROM information_schema.columns
        WHERE table_schema IN ('{schema_list}')
        ORDER BY table_schema, table_name, ordinal_position
        """
        try:
            columns = await self._execute_sql_raw(query)
        except Exception as e:
            logger.error(f"generate_typescript_types 查询失败: {e}")
            return to_json({"success": False, "error": str(e)})

        ts_code = self._build_typescript_types(columns, schemas)
        return to_json({"success": True, "typescript": ts_code})

    # ── TypeScript 类型生成辅助方法 ───────────────────────────────────────────

    def _to_ts_type(self, data_type: str, udt_name: str) -> str:
        dt = (data_type or "").lower()
        udt = (udt_name or "").lower()
        if dt in {"smallint", "integer", "bigint", "numeric", "decimal", "real", "double precision"}:
            return "number"
        if dt == "boolean":
            return "boolean"
        if dt in {"json", "jsonb"}:
            return "Json"
        if dt in {"date", "timestamp without time zone", "timestamp with time zone",
                  "time without time zone", "time with time zone", "bytea"}:
            return "string"
        if dt == "array":
            base = udt[1:] if udt.startswith("_") else udt
            return f"{self._to_ts_type(base, base)}[]"
        if udt in {"uuid", "varchar", "text", "bpchar", "name", "citext", "inet"}:
            return "string"
        if udt in {"int2", "int4", "int8", "float4", "float8"}:
            return "number"
        if udt == "bool":
            return "boolean"
        if udt in {"json", "jsonb"}:
            return "Json"
        return "string"

    def _to_ts_key(self, key: str) -> str:
        if key.replace("_", "").isalnum() and not key[0].isdigit():
            return key
        escaped = key.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    def _build_typescript_types(self, columns: List[dict], schemas: List[str]) -> str:
        grouped: dict[str, dict[str, list]] = {}
        for col in columns:
            s = col.get("table_schema", "public")
            t = col.get("table_name", "")
            grouped.setdefault(s, {}).setdefault(t, []).append(col)

        lines = [
            "export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]",
            "",
            "export type Database = {",
        ]

        for schema_name in sorted(grouped):
            tables = grouped[schema_name]
            lines.append(f"  {self._to_ts_key(schema_name)}: {{")
            lines.append("    Tables: {")
            for table_name in sorted(tables):
                table_columns = tables[table_name]
                lines.append(f"      {self._to_ts_key(table_name)}: {{")
                lines.append("        Row: {")
                for col in table_columns:
                    ts_key = self._to_ts_key(col["column_name"])
                    base = self._to_ts_type(col.get("data_type", ""), col.get("udt_name", ""))
                    nullable = col.get("is_nullable") == "YES"
                    lines.append(f"          {ts_key}: {base + ' | null' if nullable else base}")
                lines.append("        }")
                lines.append("        Insert: {")
                for col in table_columns:
                    ts_key = self._to_ts_key(col["column_name"])
                    base = self._to_ts_type(col.get("data_type", ""), col.get("udt_name", ""))
                    nullable = col.get("is_nullable") == "YES"
                    optional = nullable or col.get("column_default") is not None or col.get("is_identity") == "YES"
                    insert_type = base + " | null" if nullable else base
                    lines.append(f"          {ts_key}{'?' if optional else ''}: {insert_type}")
                lines.append("        }")
                lines.append("        Update: {")
                for col in table_columns:
                    ts_key = self._to_ts_key(col["column_name"])
                    base = self._to_ts_type(col.get("data_type", ""), col.get("udt_name", ""))
                    nullable = col.get("is_nullable") == "YES"
                    lines.append(f"          {ts_key}?: {base + ' | null' if nullable else base}")
                lines.append("        }")
                lines.append("      }")
            lines.append("    }")
            lines.append("    Views: {}")
            lines.append("    Functions: {}")
            lines.append("    Enums: {}")
            lines.append("    CompositeTypes: {}")
            lines.append("  }")

        lines.append("}")
        return "\n".join(lines)

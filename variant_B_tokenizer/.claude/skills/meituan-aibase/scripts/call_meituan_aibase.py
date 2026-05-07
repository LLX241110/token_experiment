#!/usr/bin/env python3
"""
美团 AI Base CLI
version: 0.2.0

AI Base 100% 兼容 Supabase/PostgreSQL 语法，基于 PostgREST 提供 REST API。

用法：
    uv run ./scripts/call_meituan_aibase.py <action> [options]

环境变量（数据库操作，可选——未设置时自动从管控面默认 branch 获取）：
    AIBASE_BRANCH_URL      - AI Base branch 连接地址（来自 branch.domain，通过 list-branches 获取）
    AIBASE_BRANCH_KEY      - AI Base branch API Key（来自 branch.serviceRoleKey）
    （兼容旧名称：AIBASE_WORKSPACE_URL / AIBASE_WORKSPACE_KEY，效果相同）

环境变量（可选，管控面操作）：
    AIBASE_ACCESS_TOKEN    - 美团 SSO Token，用于管控面 API（list-workspaces 等）
    AIBASE_MGMT_ENDPOINT   - 管控面 API 地址（默认 https://aibase-workspace.sankuai.com/api/v1）
    READ_ONLY=true         - 只读模式，禁止写操作
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional


# ── 支持的 Action 分组 ────────────────────────────────────────────────────────

WORKSPACE_ACTIONS = {
    "list-workspaces",
    "describe-workspace",
    "get-workspace-url",
    "get-keys",
    "create-workspace",
    "update-workspace",
    "delete-workspace",
    "list-members",
    "add-members",
    "remove-members",
    "replace-members",
    "list-branches",
    "get-branch",
    "create-branch",
    "update-branch",
    "delete-branch",
    "set-default-branch",
    "restart-branch",
}

DATABASE_ACTIONS = {
    "execute-sql",
    "list-tables",
    "list-extensions",
    "list-migrations",
    "apply-migration",
    "generate-typescript-types",
}

ALL_ACTIONS = WORKSPACE_ACTIONS | DATABASE_ACTIONS


def _read_text(value: Optional[str], file_path: Optional[str], label: str) -> str:
    if value and file_path:
        raise ValueError(f"{label} 和 {label}-file 不能同时使用")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    if value:
        return value
    raise ValueError(f"必须提供 {label} 或 {label}-file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="美团 AI Base CLI（100% 兼容 Supabase 语法）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("action", help=f"执行动作，可选：{', '.join(sorted(ALL_ACTIONS))}")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="日志级别")
    parser.add_argument("--read-only", choices=["true", "false"],
                        default=os.getenv("READ_ONLY", "false"), help="只读模式")

    # Workspace 参数
    parser.add_argument("--workspace-uuid", help="Workspace UUID（管控面操作使用）")
    parser.add_argument("--workspace-id", help="Workspace ID（兼容旧参数，同 --workspace-uuid）")
    parser.add_argument("--workspace-name", help="新建 workspace 的名称（create-workspace）")
    parser.add_argument("--description", help="workspace 或 branch 的描述（create/update 时使用）")
    parser.add_argument("--mis-list", help="成员 mis 列表，逗号分隔（成员管理操作）")
    parser.add_argument("--reveal", action="store_true", help="明文显示 API Keys")
    # Branch 参数
    parser.add_argument("--branch-uuid", help="Branch UUID（branch 相关操作使用）")
    parser.add_argument("--branch-name", help="新建分支的名称（create-branch，仅小写字母/数字/斜杠）")
    parser.add_argument("--branch-description", help="分支描述（create-branch / update-branch）")
    parser.add_argument("--parent-branch-uuid", help="父分支 UUID（create-branch 克隆时使用，可选）")

    # Database 参数
    parser.add_argument("--query", help="SQL 语句")
    parser.add_argument("--query-file", help="SQL 文件路径")
    parser.add_argument("--schemas", default="public", help="Schema 列表，逗号分隔，如 public,auth")
    parser.add_argument("--name", help="迁移名称（apply-migration 必填）")

    return parser


async def run_action(args: argparse.Namespace) -> str:
    # 覆盖 READ_ONLY 环境变量
    if args.read_only == "true":
        os.environ["READ_ONLY"] = "true"

    from meituan_aibase.platform import AiBaseClient
    from meituan_aibase.tools import WorkspaceTools, DatabaseTools

    aibase = AiBaseClient()
    workspace_tools = WorkspaceTools(aibase)
    database_tools = DatabaseTools(aibase)

    action = args.action
    # 兼容两种参数名
    workspace_uuid = args.workspace_uuid or args.workspace_id

    def _parse_mis_list() -> list[str]:
        if not args.mis_list:
            raise ValueError("此操作需要 --mis-list 参数（逗号分隔的 mis 列表）")
        return [m.strip() for m in args.mis_list.split(",") if m.strip()]

    # ── 工作区操作 ────────────────────────────────────────────────────────────
    if action == "list-workspaces":
        return await workspace_tools.list_workspaces()

    if action == "describe-workspace":
        return await workspace_tools.describe_workspace(workspace_uuid)

    if action == "get-workspace-url":
        return await workspace_tools.get_workspace_url()

    if action == "get-keys":
        return await workspace_tools.get_keys(reveal=args.reveal)

    if action == "create-workspace":
        if not args.workspace_name:
            raise ValueError("create-workspace 需要 --workspace-name 参数")
        return await workspace_tools.create_workspace(
            args.workspace_name,
            description=args.description,
            default_branch_name=args.branch_name,
            default_branch_description=args.branch_description,
        )

    if action == "update-workspace":
        if not workspace_uuid:
            raise ValueError("update-workspace 需要 --workspace-uuid 参数")
        return await workspace_tools.update_workspace(workspace_uuid, description=args.description)

    if action == "delete-workspace":
        if not workspace_uuid:
            raise ValueError("delete-workspace 需要 --workspace-uuid 参数")
        return await workspace_tools.delete_workspace(workspace_uuid)

    if action == "list-members":
        if not workspace_uuid:
            raise ValueError("list-members 需要 --workspace-uuid 参数")
        return await workspace_tools.list_members(workspace_uuid)

    if action == "add-members":
        if not workspace_uuid:
            raise ValueError("add-members 需要 --workspace-uuid 参数")
        return await workspace_tools.add_members(workspace_uuid, _parse_mis_list())

    if action == "remove-members":
        if not workspace_uuid:
            raise ValueError("remove-members 需要 --workspace-uuid 参数")
        return await workspace_tools.remove_members(workspace_uuid, _parse_mis_list())

    if action == "replace-members":
        if not workspace_uuid:
            raise ValueError("replace-members 需要 --workspace-uuid 参数")
        return await workspace_tools.replace_members(workspace_uuid, _parse_mis_list())

    # ── Branch 操作 ───────────────────────────────────────────────────────────

    if action == "list-branches":
        if not workspace_uuid:
            raise ValueError("list-branches 需要 --workspace-uuid 参数")
        return await workspace_tools.list_branches(workspace_uuid)

    if action == "get-branch":
        if not workspace_uuid:
            raise ValueError("get-branch 需要 --workspace-uuid 参数")
        if not args.branch_uuid:
            raise ValueError("get-branch 需要 --branch-uuid 参数")
        return await workspace_tools.get_branch(workspace_uuid, args.branch_uuid)

    if action == "create-branch":
        if not workspace_uuid:
            raise ValueError("create-branch 需要 --workspace-uuid 参数")
        if not args.branch_name:
            raise ValueError("create-branch 需要 --branch-name 参数")
        return await workspace_tools.create_branch(
            workspace_uuid,
            args.branch_name,
            description=args.branch_description,
            parent_branch_uuid=args.parent_branch_uuid,
        )

    if action == "update-branch":
        if not workspace_uuid:
            raise ValueError("update-branch 需要 --workspace-uuid 参数")
        if not args.branch_uuid:
            raise ValueError("update-branch 需要 --branch-uuid 参数")
        return await workspace_tools.update_branch(
            workspace_uuid, args.branch_uuid, description=args.branch_description
        )

    if action == "delete-branch":
        if not workspace_uuid:
            raise ValueError("delete-branch 需要 --workspace-uuid 参数")
        if not args.branch_uuid:
            raise ValueError("delete-branch 需要 --branch-uuid 参数")
        return await workspace_tools.delete_branch(workspace_uuid, args.branch_uuid)

    if action == "set-default-branch":
        if not workspace_uuid:
            raise ValueError("set-default-branch 需要 --workspace-uuid 参数")
        if not args.branch_uuid:
            raise ValueError("set-default-branch 需要 --branch-uuid 参数")
        return await workspace_tools.set_default_branch(workspace_uuid, args.branch_uuid)

    if action == "restart-branch":
        if not workspace_uuid:
            raise ValueError("restart-branch 需要 --workspace-uuid 参数")
        if not args.branch_uuid:
            raise ValueError("restart-branch 需要 --branch-uuid 参数")
        return await workspace_tools.restart_branch(workspace_uuid, args.branch_uuid)

    # ── 数据库操作 ────────────────────────────────────────────────────────────
    # 若显式传了 --branch-uuid，从管控面取该 branch 的 domain/serviceRoleKey，
    # 优先级高于环境变量，确保操作目标 branch 正确。
    if action in (
        "execute-sql", "list-tables", "list-extensions",
        "list-migrations", "apply-migration", "generate-typescript-types",
    ) and args.branch_uuid:
        branch_info = aibase._get_default_branch(
            workspace_uuid=workspace_uuid,
            branch_uuid=args.branch_uuid,
        )
        if not branch_info:
            raise ValueError(
                f"未找到 branch uuid={args.branch_uuid}，"
                "请确认 --workspace-uuid 与 --branch-uuid 正确且 branch 状态为 RUNNING"
            )
        branch_url = branch_info.get("domain")
        branch_key = branch_info.get("serviceRoleKey")
        if not branch_url or not branch_key:
            raise ValueError(
                f"branch {args.branch_uuid} 的 domain 或 serviceRoleKey 为空，"
                "请确认 branch 状态为 RUNNING"
            )
        from meituan_aibase.tools import DatabaseTools as _DT
        database_tools = _DT(aibase, branch_url=branch_url, branch_key=branch_key)

    if action == "execute-sql":
        query = _read_text(args.query, args.query_file, "--query")
        return await database_tools.execute_sql(query)

    if action == "list-tables":
        schemas = [s.strip() for s in args.schemas.split(",") if s.strip()]
        return await database_tools.list_tables(schemas)

    if action == "list-extensions":
        return await database_tools.list_extensions()

    if action == "list-migrations":
        return await database_tools.list_migrations()

    if action == "apply-migration":
        if not args.name:
            raise ValueError("apply-migration 需要 --name 参数")
        query = _read_text(args.query, args.query_file, "--query")
        return await database_tools.apply_migration(args.name, query)

    if action == "generate-typescript-types":
        schemas = [s.strip() for s in args.schemas.split(",") if s.strip()]
        return await database_tools.generate_typescript_types(schemas)

    # ── 未知操作 ─────────────────────────────────────────────────────────────
    raise ValueError(
        f"不支持的操作：{action}。\n"
        f"可用操作：{', '.join(sorted(ALL_ACTIONS))}"
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(levelname)s] %(name)s - %(message)s",
    )

    # 将 scripts 目录加入 Python 路径
    scripts_dir = str(Path(__file__).parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    try:
        result = asyncio.run(run_action(args))
        print(result)
        return 0
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

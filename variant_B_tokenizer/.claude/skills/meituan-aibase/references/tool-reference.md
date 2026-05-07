# Tool Reference

## 环境变量

| 变量 | 说明 | 必须 |
|------|------|------|
| `AIBASE_BRANCH_URL` | 数据库直连 URL（如 `http://opensource-test.aibase.sankuai.com`） | 数据库操作必须 |
| `AIBASE_BRANCH_KEY` | serviceRoleKey（从 `list-workspaces` 返回值获取） | 数据库操作必须 |
| `AIBASE_ACCESS_TOKEN` | 手动指定 SSO token（跳过 browser Cookie 自动获取） | 可选 |
| `AIBASE_MGMT_ENDPOINT` | 覆盖管控面地址（默认 `https://aibase.mws.sankuai.com/workspace/api/v1`） | 可选 |
| `READ_ONLY` | 设为 `true` 时禁止所有写操作 | 可选 |

## 两套接入路径

| 层 | 动作 | 鉴权方式 | 端点 |
|----|------|---------|------|
| **管控面** | `list-workspaces`、成员管理、workspace/branch CRUD | requests + yun_portal Cookie（自动） | `https://aibase.mws.sankuai.com/workspace/api/v1` |
| **数据库** | `execute-sql`、`apply-migration`、`list-tables` 等 | `AIBASE_BRANCH_KEY`（Bearer） | `{branch.domain}/pg/query` |

> ⚠️ 数据库操作走 `/pg/query` 端点，**不走** `/rest/v1/`（Kong 鉴权层不同，serviceRoleKey 在 `/rest/v1/` 会返回 401）

> ⚠️ 新版 workspace 不再包含 domain/anonKey/serviceRoleKey，这些字段已下放到 **branch**。
> 数据库连接的 URL 和 Key 必须来自 branch 详情（`list-branches` / `get-branch` 返回的 `domain` / `serviceRoleKey` 字段），**禁止手动拼接域名格式**。
> `get-keys` 和 `get-workspace-url` 也会自动从默认 branch（defaultBranch=true）取值。

## 工作区操作

```
list-workspaces
describe-workspace [--workspace-uuid <uuid>]
create-workspace --workspace-name <name> [--description <desc>]
                 [--branch-name <default-branch-name>] [--branch-description <desc>]
update-workspace --workspace-uuid <uuid> [--description <desc>]
delete-workspace --workspace-uuid <uuid>
get-workspace-url [--workspace-uuid <uuid>] [--branch-uuid <uuid>]
get-keys [--reveal] [--workspace-uuid <uuid>] [--branch-uuid <uuid>]
```

## 成员管理

```
list-members    --workspace-uuid <uuid>
add-members     --workspace-uuid <uuid> --mis-list a,b,c
remove-members  --workspace-uuid <uuid> --mis-list a,b,c
replace-members --workspace-uuid <uuid> --mis-list a,b,c
```

## Branch 管理

```
list-branches       --workspace-uuid <uuid>
get-branch          --workspace-uuid <uuid> --branch-uuid <uuid>
create-branch       --workspace-uuid <uuid> --branch-name <name>
                    [--branch-description <desc>] [--parent-branch-uuid <uuid>]
update-branch       --workspace-uuid <uuid> --branch-uuid <uuid>
                    [--branch-description <desc>]
delete-branch       --workspace-uuid <uuid> --branch-uuid <uuid>
set-default-branch  --workspace-uuid <uuid> --branch-uuid <uuid>
restart-branch      --workspace-uuid <uuid> --branch-uuid <uuid>
```

## 数据库操作

```
execute-sql --query "SELECT 1"
execute-sql --query-file ./query.sql
list-tables [--schemas public,auth]
list-migrations
list-extensions
apply-migration --name <migration-name> --query "<DDL SQL>"
apply-migration --name <migration-name> --query-file ./migration.sql
generate-typescript-types [--schemas public,auth]
```

## 参数说明

- `--workspace-uuid`：目标 workspace UUID（从 `list-workspaces` 获取）
- `--branch-uuid`：目标 branch UUID（从 `list-branches` 获取）
- `--branch-name`：创建分支时的名称（仅小写字母、数字和斜杠，不可以斜杠开/结尾，不可含连续斜杠，最长 48 字符）
- `--branch-description`：分支描述（create-branch / update-branch 使用）
- `--parent-branch-uuid`：克隆分支时的父分支 UUID（可选，不传则创建全新空分支）
- `--description`：workspace 描述（create-workspace / update-workspace 使用）
- `--name`（apply-migration）：迁移名称，建议格式 `create_<table>_table` / `add_<column>_to_<table>`
- `--reveal`（get-keys）：明文输出 API Key，默认脱敏
- `--schemas`：逗号分隔的 schema 列表，默认 `public`

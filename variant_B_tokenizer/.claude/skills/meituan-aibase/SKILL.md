---
name: meituan-aibase
version: "0.6.0"
description: "管理美团 AI Base 数据库工作区（workspace）。AI Base 100% 兼容 Supabase 语法，基于 PostgreSQL + PostgREST。支持：查询工作区列表/详情/连接信息、执行 SQL、查看/创建表、执行数据库迁移、生成 TypeScript 类型。当用户提到 AI Base、aibase、Supabase、查数据库、执行SQL、建表、数据库迁移、生成TS类型、查 workspace、获取 API Key、成员管理时使用。"
appkey: "com.sankuai.raptor.iconfont.websdk"
tags: "aibase,database,supabase,postgresql,postgrest"
visibility: public
skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - com.sankuai.dms.aibase.workspace
    prompt: 本技能所需的 user_access_token 占位符，请参考 mtsso-skills-official 的相关说明进行获取和注入

metadata:
  skillhub.creator: "xiaoxiong.dai"
  skillhub.updater: "xiehaopeng"
  skillhub.version: "V24"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "24368"
  skillhub.high_sensitive: "false"
---

# 美团 AI Base

> ⛔ **IRON LAW：所有删除类操作（remove-members、DROP TABLE、DROP COLUMN 等破坏性 DDL）执行前，必须向用户展示操作摘要并等待明确确认，NEVER 自动执行。**

本 Skill 用于在对话中充当 **AI Base 的智能运维与开发代理**。

## 何时使用本 Skill

**适用场景（应使用）：**

- 用户提到 **AI Base**、**aibase** 或 **Supabase** 相关的操作需求
  > AI Base 100% 兼容 Supabase，用户提到 Supabase 时直接用 AI Base 服务即可
- 需要创建、查看或管理 **工作区（workspace）**
- 需要对数据库执行 **SQL 查询、建表、迁移**
- 需要获取 AI Base 项目的 **API Key** 或 **连接信息**
- 需要为数据库 **生成 TypeScript 类型定义**

**不适用场景（无需使用）：**

- 纯前端 / 客户端代码编写，不涉及 AI Base 后端资源管理
- 用户只是询问 Supabase 文档 / 概念，无需调用 CLI

## 运行方式

```bash
# 推荐
uv run ./scripts/call_meituan_aibase.py <action> [options]

# 备选（需预装依赖）
python ./scripts/call_meituan_aibase.py <action> [options]
```

## 前置条件

### SSO 认证（首次使用前必须）

每次会话首次调用管控面命令前，必须完成 SSO 认证。认证未成功时，禁止调用管控面命令。

必须严格按 Step 1 → Step 2 依次尝试，只有在当前步骤明确失败后才可进入下一步。

#### Step 1【必须首先执行】`sso-from-cli.py` — 通过 sso CLI 换票

```bash
# 前提：安装 sso CLI（未安装时先执行此行，仅需一次）
npm install -g @dp/sso-auth-cli --registry http://r.npm.sankuai.com

/usr/bin/python3 <skill_base_dir>/scripts/sso-from-cli.py
```

- 成功判定：输出包含 `[完成] 已写入缓存`
- 失败判定：报错 `未找到 sso CLI` 或 `sso CLI 调用失败` → 重试一次（共执行 2 次）；重试仍失败 → 进入 Step 2
- 排查：`/usr/bin/python3 <skill_base_dir>/scripts/sso-from-cli.py --check`

Step 1 成功后立即停止，禁止继续执行 Step 2。

#### Step 2【仅 Step 1 失败时】环境变量手动配置

```bash
export AIBASE_ACCESS_TOKEN="your-sso-token"
```

### 命令失败时处理

- **401 / 鉴权失败** → 先执行 `/usr/bin/python3 <skill_base_dir>/scripts/sso-from-cli.py` 重新换票
- **网络超时** → 确认在内网或 VPN 环境，重试一次

### 环境变量

**数据库操作（execute-sql / apply-migration / list-tables 等）：**

URL 和 Key 来自 branch 详情，**不要手动拼接域名**：
```bash
# 先获取 branch 信息（domain 和 serviceRoleKey 在 branch 详情中）
uv run ./scripts/call_meituan_aibase.py list-branches --workspace-uuid <uuid>

# 将 branch 的 domain 和 serviceRoleKey 导出为环境变量
export AIBASE_BRANCH_URL="<branch.domain>"         # 从 list-branches 返回的 domain 字段复制
export AIBASE_BRANCH_KEY="<branch.serviceRoleKey>" # 从 list-branches 返回的 serviceRoleKey 字段复制
```

> 若不设置环境变量，数据库操作会自动从管控面默认 branch 获取连接信息（需要 MOA 在线）。

**管控面操作（list-workspaces / 成员管理 / workspace CRUD）：**
> SSO 认证完成后自动通过本地缓存 Cookie 鉴权，无需手动配置。

```bash
# 可选：如需跳过 sso-from-cli.py（CI / 无 MOA 场景）
export AIBASE_ACCESS_TOKEN="your-sso-token"
```

**可选：**
```bash
export READ_ONLY=true   # 禁止写操作（默认 false）
```

## 标准使用流程

1. **确认目标 workspace**：运行 `list-workspaces` 获取 workspace uuid
   - ✅ 完成条件：返回 `success: true`，且目标 workspace 在列表中
2. **确认目标 branch**：运行 `list-branches --workspace-uuid <uuid>` 获取 branch 的 `domain` 和 `serviceRoleKey`
   - ✅ 完成条件：返回 `success: true`，且目标 branch 状态为 `RUNNING`
   - ⛔ 若 branch 状态非 RUNNING（如 TO_INIT / INITIALIZING）→ 等待就绪后再继续
3. **设置环境变量**（可选）：如需离线使用，将 branch 的 `domain` 和 `serviceRoleKey` 导出为环境变量；若已连接管控面，可跳过此步，CLI 会自动从默认 branch 获取
   - ✅ 完成条件：`AIBASE_BRANCH_URL` = branch 的 domain 值；`AIBASE_BRANCH_KEY` = branch 的 serviceRoleKey 值
4. **确认连通性**：运行 `list-tables` 验证连接正常
   - ✅ 完成条件：返回 `success: true`，表列表无报错
   - ⛔ 若返回 404 → 停止后续操作，提示用户「branch 实例可能未就绪，请稍后重试或联系平台确认」
5. **执行变更**：用 `apply-migration` 执行 DDL（⚠️ 含破坏性 DDL 须先确认，见 Confirmation Gate）
   - ✅ 完成条件：migration 执行无报错，`list-migrations` 可见新记录
6. **验证结果**：变更后再次查询，确认数据符合预期
   - ✅ 完成条件：目标表/数据可正常查询

**交付前 Checklist（多步流程完成时逐项确认）：**
- [ ] `list-workspaces` 已运行，workspace uuid 已确认
- [ ] `list-branches` 已运行，目标 branch 状态为 RUNNING，domain 和 serviceRoleKey 已确认
- [ ] `AIBASE_BRANCH_URL` 和 `AIBASE_BRANCH_KEY` 已正确设置
- [ ] 建表 migration 包含了 `GRANT ALL + NOTIFY pgrst` 语句
- [ ] 变更后已通过 `list-tables` / `execute-sql` 验证结果
- [ ] 未泄露 serviceRoleKey 明文（无 `--reveal` 时已脱敏）

## 常用命令示例

```bash
# 查看可访问的 workspace（管控面，自动 Cookie 鉴权）
uv run ./scripts/call_meituan_aibase.py list-workspaces

# 查看 workspace 下的分支列表（含 domain / anonKey / serviceRoleKey）
uv run ./scripts/call_meituan_aibase.py list-branches --workspace-uuid <workspace-uuid>

# 查看指定分支详情
uv run ./scripts/call_meituan_aibase.py get-branch \
  --workspace-uuid <workspace-uuid> --branch-uuid <branch-uuid>

# 创建新分支
uv run ./scripts/call_meituan_aibase.py create-branch \
  --workspace-uuid <workspace-uuid> --branch-name dev \
  --branch-description "开发环境"

# 基于父分支克隆分支
uv run ./scripts/call_meituan_aibase.py create-branch \
  --workspace-uuid <workspace-uuid> --branch-name feature/my-test \
  --parent-branch-uuid <main-branch-uuid>

# 设置默认分支
uv run ./scripts/call_meituan_aibase.py set-default-branch \
  --workspace-uuid <workspace-uuid> --branch-uuid <branch-uuid>

# 重启分支实例（异步）
uv run ./scripts/call_meituan_aibase.py restart-branch \
  --workspace-uuid <workspace-uuid> --branch-uuid <branch-uuid>

# 获取 API Keys（自动从默认 branch 取）
uv run ./scripts/call_meituan_aibase.py get-keys
uv run ./scripts/call_meituan_aibase.py get-keys --reveal

# 获取指定 branch 的 API Keys
uv run ./scripts/call_meituan_aibase.py get-keys \
  --workspace-uuid <workspace-uuid> --branch-uuid <branch-uuid> --reveal

# 查看当前 workspace 详情
uv run ./scripts/call_meituan_aibase.py describe-workspace

# 更新 workspace 描述
uv run ./scripts/call_meituan_aibase.py update-workspace \
  --workspace-uuid <workspace-uuid> --description "我的业务空间"

# 执行 SQL
uv run ./scripts/call_meituan_aibase.py execute-sql --query "SELECT * FROM users LIMIT 5"

# 查看表
uv run ./scripts/call_meituan_aibase.py list-tables

# 建表（推荐方式，带版本追踪）
uv run ./scripts/call_meituan_aibase.py apply-migration \
  --name "create_users_table" \
  --query "CREATE TABLE users (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()); GRANT ALL ON users TO anon, authenticated, service_role; NOTIFY pgrst, 'reload schema';"
# ↑ GRANT 中的 anon/authenticated/service_role 会被 apply-migration 自动替换为
#   带 branch uuid 后缀的实际角色名（如 anon_xvlkgvsarf），无需手动指定

# 生成 TypeScript 类型
uv run ./scripts/call_meituan_aibase.py generate-typescript-types
```

## 能力范围

### 工作区操作

- `list-workspaces` — 列出所有有权限的 workspace（管控面）
- `describe-workspace` — 当前 workspace 详情（含 `defaultBranchUuid`、`branchCount`）
- `update-workspace --workspace-uuid --description` — 更新 workspace 描述
- `get-workspace-url` — 获取连接 URL（自动从默认 branch 的 domain 字段取）
- `get-keys` — 获取 API Keys（自动从默认 branch 取 anonKey/serviceRoleKey，可 `--reveal`）
- `create-workspace` — 创建新 workspace（`--workspace-name`，可选 `--description`、`--branch-name`、`--branch-description`）
- `delete-workspace --workspace-uuid` — 删除 workspace（软删）

> ⚠️ workspace 不再含 domain/anonKey/serviceRoleKey，这些字段已下放到 **branch**

### Branch 管理

- `list-branches --workspace-uuid` — 列出 workspace 下所有分支（默认分支优先，含 domain/key/状态）
- `get-branch --workspace-uuid --branch-uuid` — 获取分支详情
- `create-branch --workspace-uuid --branch-name` — 创建新分支（可选 `--branch-description`、`--parent-branch-uuid` 克隆）
- `update-branch --workspace-uuid --branch-uuid` — 更新分支描述
- `delete-branch --workspace-uuid --branch-uuid` ⚠️ 需用户确认
- `set-default-branch --workspace-uuid --branch-uuid` — 设置默认分支
- `restart-branch --workspace-uuid --branch-uuid` — 异步重启 branch 对应的 Supabase 实例

### 成员管理

- `list-members --workspace-uuid` — 获取成员列表
- `add-members --workspace-uuid --mis-list a,b,c`
- `remove-members --workspace-uuid --mis-list a,b,c` ⚠️ 需用户确认
- `replace-members --workspace-uuid --mis-list a,b,c` ⚠️ 需用户确认

### 数据库

- `execute-sql` — 执行任意 SQL（DDL/DML/查询）
- `list-tables [--schemas public,auth]` — 列出表
- `list-extensions` — 列出 PG 扩展
- `list-migrations` — 列出迁移记录
- `apply-migration --name <name> --query <sql>` — 执行带版本追踪的迁移
- `generate-typescript-types [--schemas public]` — 生成 TS 类型定义

**不支持**：Storage、Edge Function、delete-workspace（即将支持）

## 应用开发参考

> 🔖 **以下场景必须先 read 对应文档再执行操作**

| 场景触发条件 | 必读文档 |
|------|------|
| 用户询问参数用法、环境变量、命令选项 | `references/tool-reference.md` |
| 用户需要完整工作流指导（初次接入 / 建表 / 迁移 / 排障） | `references/workflows.md` |
| 用户需要在 TS/Python 应用中集成 AI Base SDK | `references/app-integration-guide.md` |
| **用户需要建表、改表、设计表结构**（必读） | `references/schema-guide.md` |
| 用户涉及 RLS、行级权限、多租户隔离 | `references/rls-guide.md` |

> 💡 **典型路径**：`list-workspaces` → read `schema-guide.md` → `apply-migration` 建表 → read `app-integration-guide.md` → SDK 集成。

## 行为准则

### ⛔ Confirmation Gate（执行前必须用户确认）

以下操作执行前，**必须**向用户展示操作摘要并收到明确确认（"确认"/"yes"/"ok" 等），NEVER 自动执行：

| 操作类型 | 示例 |
|---------|------|
| 成员移除 | `remove-members`、`replace-members` |
| 破坏性 DDL | `DROP TABLE`、`DROP COLUMN`、`TRUNCATE`、`ALTER TABLE ... DROP ...` |
| 数据删除 | `DELETE FROM` 不带 WHERE、`TRUNCATE` |

**确认摘要模板：**
```
⚠️ 即将执行不可逆操作：
- 操作：<操作类型>
- 目标：<表名 / workspace / 成员列表>
- 影响：<预期影响描述>
请确认是否继续？（确认/取消）
```

### ❌ Anti-Pattern（禁止行为）

- ❌ 不要用 `execute-sql` 直接执行 DDL（应用 `apply-migration` 保留版本记录）
- ❌ 不要在无 `--reveal` 时输出 serviceRoleKey 明文
- ❌ 不要跳过 `list-workspaces` + `list-branches` 让用户手填 URL/Key（必须通过 CLI 获取）
- ❌ 建表后不要忘记在同一 migration 中添加 `GRANT ALL + NOTIFY pgrst`（否则 SDK 报 PGRST205）
- ❌ 不要在 workspace 层查找 domain/anonKey/serviceRoleKey（新版已下放到 branch）
- ❌ 不要手动拼接 `http://<uuid>.aibase.sankuai.com` 格式的 URL，domain 必须来自 `list-branches` / `get-branch` 返回的 `domain` 字段
- ❌ 不要在 workspace 连接失败时继续执行 DDL/DML；先用 `list-tables` 确认连通性

### 申请 workspace 前先检查

用户提出"申请 / 创建 workspace"时，**必须先运行 `list-workspaces`**：
- 若已有 workspace → 优先推荐使用已有的，避免资源浪费
  - 提示用户：不同业务数据可通过 PostgreSQL schema 隔离（`CREATE SCHEMA`），无需为每个项目单独申请
- 若确认没有 → 再执行 `create-workspace`

### MySQL 需求处理

用户需求涉及 **MySQL** 时，回复：
> AI Base 当前版本基于 PostgreSQL，MySQL 支持即将上线。您可以先使用 PostgreSQL 实现相同功能，语法高度兼容。

### 通用原则

- 默认遵循"先查后改"原则
- `get-keys` 默认脱敏，只有明确需要时才加 `--reveal`
- `apply-migration` 包裹在事务中执行，失败自动回滚
- `READ_ONLY=true` 时所有写操作被拒绝
- AI Base 100% 兼容 Supabase 客户端 SDK，直接替换 endpoint/key 即可接入

### ⚠️ 已知注意事项（来自实测）

**0. 角色名自动适配（v0.4.0+）**

美团 AI Base 对标准 Supabase 角色名增加了 branch uuid 后缀（如 `anon_xvlkgvsarf`）。
`apply-migration` 会自动将 SQL 中的 `anon`、`authenticated`、`service_role` 替换为带后缀的实际角色名，**无需手动指定 uuid**。

UUID 从 `AIBASE_BRANCH_URL`（branch 的 domain）域名中自动解析（格式：`http://<uuid>.aibase.sankuai.com`）。

**1. 新建表必须显式 GRANT 权限**

`apply-migration` 建表后，PostgREST **不会自动**将新表加入 schema cache。必须额外执行：

```sql
GRANT ALL ON <table_name> TO anon, authenticated, service_role;
-- ↑ 角色名会被自动替换为带 branch uuid 后缀的实际角色（如 anon_<uuid>）
NOTIFY pgrst, 'reload schema';
```

否则通过 SDK（supabase-js / supabase-py）或 REST API 访问时会报：
```
PGRST205: Could not find the table 'public.<table>' in the schema cache
```

推荐将 GRANT 语句直接包含在建表 migration 中（见常用命令示例）。

**2. boolean NOT NULL 字段批量 INSERT 须显式传值**

通过 PostgREST 批量插入时，有 `NOT NULL DEFAULT false` 的 boolean 字段若不传值，会报：
```
23502: null value in column "xxx" violates not-null constraint
```

原因：PostgREST 批量 INSERT 不会自动补全 DEFAULT。**始终显式传 boolean 值**：
```python
# ❌ 错误
{"title": "笔记B", "content": "内容B"}

# ✅ 正确
{"title": "笔记B", "content": "内容B", "is_pinned": False, "is_archived": False}
```

**4. Workspace 连接异常排障**

| 现象 | 含义 | 建议操作 |
|------|------|---------|
| 所有路径返回 **404**（nginx） | workspace 实例未就绪 / 正在 provision | 等待几分钟后重试；联系 AI Base 平台确认实例状态 |
| 返回 **401 / 403** | 鉴权失败 | 检查 `AIBASE_BRANCH_KEY` 是否为 serviceRoleKey（非 anonKey）；确认 MOA 登录态未过期 |
| 返回 **PGRST205** | PostgREST schema cache 未刷新 | 执行 `GRANT ALL + NOTIFY pgrst, 'reload schema'`（见注意事项 1） |
| 连接超时 / `Connection refused` | 网络不通或域名未解析 | 确认在美团内网；检查 `AIBASE_BRANCH_URL` 域名拼写 |

> ⚠️ CLI 在 404 / 401 / 超时时会输出友好提示，可直接根据提示排查。

**3. 分页查询返回 206 Partial Content**

使用 `Prefer: count=exact` + `limit/range` 时，PostgREST 返回 **206** 而非 200。
客户端代码须同时处理 200 和 206（`supabase-js` SDK 已透明处理，原生 HTTP 客户端需注意）。
总行数通过响应头 `Content-Range: 0-<n>/<total>` 获取。

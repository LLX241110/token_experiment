"""
AI Base Skill 配置模块
version: 0.4.0

SSO 鉴权：
  管控面接口（list-workspaces 等）通过美团 SSO 用户身份票（user_access_token）鉴权。
  取票优先级：
    1. 环境变量 AIBASE_ACCESS_TOKEN（向后兼容，供无 MOA 场景或 CI 使用）
    2. 本地缓存 ~/.meituan_sso/aibase_sso.json（sso-from-cli.py 注入）
    3. npx mtsso-moa-local-exchange 自动从本地 MOA 无感获取（运行时调用）

  audience: com.sankuai.dms.aibase.workspace

重要概念：
  workspace  - 业务分组容器，不对应任何实例，无 domain/key 字段
  branch     - 对应一个独立的 AI Base（Supabase）实例，含 domain/anonKey/serviceRoleKey
  数据库连接 URL 和 Key 均来自 branch，不来自 workspace
"""
import os
import re
import logging
import subprocess
import json
import time

logger = logging.getLogger(__name__)

# ── 只读模式 ──────────────────────────────────────────────────────────────────
READ_ONLY = os.getenv("READ_ONLY", "false").lower() == "true"

# ── Branch 接入配置（从 branch 详情获取，不要手动拼接域名）────────────────────
# URL 来自 branch.domain，Key 来自 branch.serviceRoleKey
# 若未设置，数据库操作将自动从管控面默认 branch 获取（需 MOA 在线）
AIBASE_BRANCH_URL = os.getenv("AIBASE_BRANCH_URL", "").strip()
AIBASE_BRANCH_KEY = os.getenv("AIBASE_BRANCH_KEY", "").strip()

# 向后兼容旧环境变量名（WORKSPACE_URL / WORKSPACE_KEY）
# 优先使用新名称；若新名称未设置，自动 fallback 到旧名称
if not AIBASE_BRANCH_URL:
    AIBASE_BRANCH_URL = os.getenv("AIBASE_WORKSPACE_URL", "").strip()
if not AIBASE_BRANCH_KEY:
    AIBASE_BRANCH_KEY = os.getenv("AIBASE_WORKSPACE_KEY", "").strip()

# ── 管控面配置 ────────────────────────────────────────────────────────────────
# 管控面 API 地址（线上）
AIBASE_MGMT_ENDPOINT = os.getenv(
    "AIBASE_MGMT_ENDPOINT",
    "https://aibase.mws.sankuai.com/workspace/api/v1"
).strip()

# 兼容旧变量名
AIBASE_API_ENDPOINT = os.getenv("AIBASE_API_ENDPOINT", AIBASE_MGMT_ENDPOINT).strip()

# 注：管控面地址历史变更记录
#   旧地址（v0.2.0）：https://aibase-workspace.sankuai.com/api/v1
#   新地址（v0.3.0+）：https://aibase.mws.sankuai.com/workspace/api/v1
#   域名结构：{host}/workspace  +  /api/v1（OpenAPI 固定 Base URL）  +  /{resource}

# SSO audience：MWS 网关（openresty yun_portal）的 client_id
# 管控面 *.mws.sankuai.com 使用 yun_portal_ssoid Cookie 鉴权，
# 对应 audience 为 60921859，参见 SSO 接入指南 FAQ#14
# https://km.sankuai.com/collabpage/2751640363
AIBASE_SSO_AUDIENCE = "60921859"

# ── SSO Token 获取 ────────────────────────────────────────────────────────────
# 管控面认证 Token
# 优先从环境变量读取（向后兼容），为空则在运行时通过 _get_sso_token() 自动取票
AIBASE_ACCESS_TOKEN = os.getenv("AIBASE_ACCESS_TOKEN", "").strip()


def get_branch_uuid_from_url(url: str = "") -> str:
    """
    从 branch domain URL 中解析 branch uuid（用于 PG 角色名后缀替换）。

    domain 格式：http://<branch-uuid>.aibase.sankuai.com[/...]
    UUID 来源：branch 详情的 domain 字段（通过 list-branches / get-branch 获取），
              或环境变量 AIBASE_BRANCH_URL。

    返回 uuid 字符串，解析失败返回空字符串。
    """
    target = url or AIBASE_BRANCH_URL
    m = re.match(r"https?://([^.]+)\.aibase\.sankuai\.com", target)
    return m.group(1) if m else ""


# 向后兼容别名
get_workspace_uuid_from_url = get_branch_uuid_from_url


def resolve_pg_roles(sql: str, branch_uuid: str = "") -> str:
    """
    将 SQL 中标准 Supabase 角色名（anon / authenticated / service_role）
    替换为带 branch uuid 后缀的实际角色名。

    美团 AI Base 对每个 branch 的角色命名规则：
      anon             → anon_<branch-uuid>
      authenticated    → authenticated_<branch-uuid>
      service_role     → service_role_<branch-uuid>

    仅在 uuid 非空时执行替换；uuid 为空则原样返回。
    uuid 来源（优先级）：
      1. 参数 branch_uuid（显式传入）
      2. AIBASE_BRANCH_URL 环境变量的域名部分
    """
    if not branch_uuid:
        branch_uuid = get_branch_uuid_from_url()
    if not branch_uuid:
        return sql

    # 替换顺序：先替换较长的 service_role / authenticated，再替换 anon，
    # 避免 anon 匹配到 anonymous 等其他单词（用单词边界 \b 保护）
    for role in ("service_role", "authenticated", "anon"):
        suffixed = f"{role}_{branch_uuid}"
        # 只替换还未带后缀的角色名（避免重复添加后缀）
        sql = re.sub(rf"\b{role}\b(?!_)", suffixed, sql)
    return sql


# ── 本地 SSO 缓存 ─────────────────────────────────────────────────────────────
_SSO_CACHE_FILE = os.path.expanduser("~/.meituan_sso/aibase_sso.json")
def _load_cached_sso_token() -> str:
    """从 sso-from-cli.py 写入的本地缓存读取 SSO token。
    Returns:
        token 字符串（未过期时），空字符串表示无缓存或已过期。
    """
    if not os.path.exists(_SSO_CACHE_FILE):
        return ""
    try:
        with open(_SSO_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""
    token = data.get("cookie_value", "")
    if not token:
        return ""
    obtained_at = data.get("obtained_at", 0)
    expires_in = data.get("expires_in", 7200)
    if time.time() - obtained_at >= expires_in:
        logger.debug("本地 SSO 缓存已过期")
        return ""
    return token


def get_sso_token(audience: str = AIBASE_SSO_AUDIENCE) -> str:
    """
    获取美团 SSO 用户身份票据。
    取票策略：
      1. 环境变量 AIBASE_ACCESS_TOKEN（已有则直接返回）
      2. 本地缓存 ~/.meituan_sso/aibase_sso.json（sso-from-cli.py 注入）
      3. npx mtsso-moa-local-exchange --audience <audience>（本地 MOA 无感取票）

    返回 access_token 字符串，失败时抛出 RuntimeError。
    """
    # 1. 环境变量 fallback
    env_token = os.getenv("AIBASE_ACCESS_TOKEN", "").strip()
    if env_token:
        logger.debug("使用 AIBASE_ACCESS_TOKEN 环境变量中的 token")
        return env_token

    # 2. 本地缓存（sso-from-cli.py 注入）
    cached_token = _load_cached_sso_token()
    if cached_token:
        logger.info("使用本地缓存的 SSO token（sso-from-cli.py 注入）")
        return cached_token

    # 3. MOA 无感取票
    logger.info(f"正在通过 MOA 获取 SSO token（audience={audience}）...")
    try:
        result = subprocess.run(
            ["npx", "--yes", "mtsso-moa-local-exchange", "--audience", audience],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"mtsso-moa-local-exchange 失败（exit={result.returncode}）: {stderr}")
        output = result.stdout.strip()
        # 输出为 JSON，提取 access_token
        try:
            data = json.loads(output)
            token = data.get("access_token", "")
        except json.JSONDecodeError:
            # 有时输出包含多行，找最后一段 JSON
            for line in reversed(output.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        token = data.get("access_token", "")
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                raise RuntimeError(f"无法解析 mtsso-moa-local-exchange 输出: {output[:200]}")
        if not token:
            raise RuntimeError("mtsso-moa-local-exchange 返回了空 access_token")
        logger.info("✅ SSO token 获取成功（via MOA 无感登录）")
        return token
    except FileNotFoundError:
        raise RuntimeError(
            "未找到 npx 命令，无法自动获取 SSO token。\n"
            "请手动设置：export AIBASE_ACCESS_TOKEN=<your-sso-token>"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "MOA 无感取票超时（30s）。请确认 MOA 已安装并登录，"
            "或手动设置 AIBASE_ACCESS_TOKEN 环境变量。"
        )


# ── 校验 ──────────────────────────────────────────────────────────────────────
if not AIBASE_BRANCH_URL:
    logger.warning(
        "AIBASE_BRANCH_URL 未设置。数据库操作将尝试从管控面默认 branch 自动获取连接信息。"
        "如需手动指定，请先运行 list-branches 获取 branch domain，再设置此变量。"
    )

if not AIBASE_BRANCH_KEY:
    logger.warning(
        "AIBASE_BRANCH_KEY 未设置。数据库操作将尝试从管控面默认 branch 自动获取 serviceRoleKey。"
        "如需手动指定，请先运行 list-branches 获取 branch serviceRoleKey，再设置此变量。"
    )

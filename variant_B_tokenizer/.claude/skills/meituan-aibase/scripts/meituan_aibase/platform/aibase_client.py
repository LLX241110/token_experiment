"""
AI Base 管控面客户端
version: 0.5.0

接口文档：https://aibase.mws.sankuai.com/workspace/api/v1

  Workspace：
    GET    /workspaces                                              列出当前用户所有 workspace
    POST   /workspaces                                             创建 workspace
    PUT    /workspaces/{workspaceUuid}                             更新 workspace（描述）
    DELETE /workspaces/{workspaceUuid}                             删除 workspace（软删）

  Workspace 成员：
    GET    /workspaces/{workspaceUuid}/members                     获取成员列表
    POST   /workspaces/{workspaceUuid}/members                     批量添加成员
    DELETE /workspaces/{workspaceUuid}/members                     批量删除成员
    PUT    /workspaces/{workspaceUuid}/members                     全量覆盖成员列表

  Workspace 分支（Branch）：
    GET    /workspaces/{workspaceUuid}/branches                    获取分支列表
    POST   /workspaces/{workspaceUuid}/branches                    创建分支
    GET    /workspaces/{workspaceUuid}/branches/{branchUuid}       获取分支详情
    PUT    /workspaces/{workspaceUuid}/branches/{branchUuid}       更新分支（描述）
    DELETE /workspaces/{workspaceUuid}/branches/{branchUuid}       删除分支
    POST   /workspaces/{workspaceUuid}/branches/{branchUuid}/set-default  设置默认分支
    POST   /workspaces/{workspaceUuid}/branches/{branchUuid}/restart      重启分支实例

响应体约定：
  { "code": 0, "data": ..., "userMessage": "...", "ctx": { "traceId": "" } }
  code=0 为成功，否则为业务错误。

注意：workspace 不再承载实例字段（domain/anonKey/serviceRoleKey）。
  这些字段已下放到 branch。可将原先的 workspace 实例理解为
  defaultBranchName=main 的默认分支。

鉴权方案（v0.4.0+）：
  MWS 域名（*.mws.sankuai.com）统一走 openresty yun_portal Cookie 鉴权。
  本版本通过 Python requests 直接发 HTTP，将 SSO user_access_token 注入
  Cookie（yun_portal_ssoid=<token>），无需依赖 agent-browser。

  参考：SSO 接入指南 FAQ#14
    https://km.sankuai.com/collabpage/2751640363

  取票优先级（见 config.get_sso_token）：
    1. 环境变量 AIBASE_ACCESS_TOKEN（向后兼容）
    2. 命令行参数 --access-token（由 SKILL.md ${user_access_token} 占位符注入）
    3. npx mtsso-moa-local-exchange 自动从本地 MOA 无感获取
"""
import json
import logging
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from ..config import (
    AIBASE_MGMT_ENDPOINT,
    AIBASE_ACCESS_TOKEN,
    AIBASE_BRANCH_URL,
    AIBASE_BRANCH_KEY,
    get_sso_token,
)

logger = logging.getLogger(__name__)

# Skill 版本（传给管控面 skillVersion query 参数，供服务端版本校验使用）
SKILL_VERSION = "0.6.0"

# HTTP 请求超时（秒）
_REQUEST_TIMEOUT = 15


class AiBaseApiError(Exception):
    def __init__(self, code: int, user_message: str, message: str, trace_id: str = ""):
        self.code = code
        self.user_message = user_message
        self.message = message
        self.trace_id = trace_id
        super().__init__(f"[{code}] {message} (traceId={trace_id})")


def _raise_if_error(resp_json: dict) -> None:
    code = resp_json.get("code", -1)
    if code != 0:
        raise AiBaseApiError(
            code=code,
            user_message=resp_json.get("userMessage", ""),
            message=resp_json.get("message", "unknown error"),
            trace_id=resp_json.get("ctx", {}).get("traceId", ""),
        )


def _fetch_json_direct(
    method: str,
    url: str,
    body: Optional[dict] = None,
    sso_token: str = "",
    timeout: int = _REQUEST_TIMEOUT,
) -> dict:
    """
    直接通过 requests 调用管控面 HTTP 接口。
    将 SSO token 以 yun_portal_ssoid Cookie 形式传递，完成 MWS 网关鉴权。
    """
    if not sso_token:
        raise RuntimeError(
            "SSO token 为空，无法请求管控面接口。\n"
            "请确认 MOA 已安装并登录，或设置环境变量 AIBASE_ACCESS_TOKEN。"
        )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    cookies = {"yun_portal_ssoid": sso_token}

    try:
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            cookies=cookies,
            json=body if body is not None else None,
            timeout=timeout,
            verify=False,
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(f"请求超时（{timeout}s）：{url}")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"网络连接失败：{url}\n原因：{e}")

    # HTTP 层错误
    if resp.status_code == 401 or resp.status_code == 403:
        raise RuntimeError(
            f"鉴权失败（HTTP {resp.status_code}）：SSO token 可能已过期或无权限。\n"
            "请确认 MOA 已登录，或重新设置 AIBASE_ACCESS_TOKEN 环境变量。"
        )
    if resp.status_code == 404:
        raise RuntimeError(
            f"接口不存在（HTTP 404）：{url}\n"
            "可能原因：workspace 尚未就绪（新建后需几分钟初始化），请稍后重试。"
        )
    if not resp.ok:
        raise RuntimeError(
            f"HTTP {resp.status_code}：{resp.text[:200]}"
        )

    # 解析响应体
    try:
        return resp.json()
    except Exception as e:
        raise RuntimeError(f"管控面响应解析失败: {e}\n原始内容: {resp.text[:500]}")


class AiBaseClient:
    """
    AI Base 管控面客户端 v0.4.0

    直接通过 requests 发 HTTP，将 SSO user_access_token 以 Cookie 形式
    （yun_portal_ssoid）传入，完成 MWS 网关鉴权。无需 agent-browser。

    取票优先级：环境变量 AIBASE_ACCESS_TOKEN > CLI --access-token > MOA 无感换票。
    """

    def __init__(self, access_token: Optional[str] = None) -> None:
        self._endpoint = AIBASE_MGMT_ENDPOINT.rstrip("/")
        # CLI 传入的 token 优先于环境变量
        self._token: str = access_token or AIBASE_ACCESS_TOKEN or ""
        self._token_fetched = bool(self._token)
        logger.info(f"AI Base 管控面 endpoint：{self._endpoint}")

    def _ensure_token(self) -> None:
        """延迟取票：仅在第一次需要时调用 MOA 换票。"""
        if self._token_fetched:
            return
        self._token = get_sso_token()
        self._token_fetched = True
        logger.info("SSO token 自动获取成功")

    def _url(self, path: str) -> str:
        sep = "&" if "?" in path else "?"
        return f"{self._endpoint}{path}{sep}skillVersion={SKILL_VERSION}"

    def _fetch(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        """统一入口：确保 token → 发请求。"""
        self._ensure_token()
        return _fetch_json_direct(
            method=method,
            url=self._url(path),
            body=body,
            sso_token=self._token,
        )

    # ── Workspace 接口 ────────────────────────────────────────────────────────

    def list_workspaces(self) -> list[dict]:
        """GET /workspaces — 列出当前用户有权限的所有 workspace"""
        resp = self._fetch("GET", "/workspaces")
        _raise_if_error(resp)
        data = resp.get("data") or []
        return data if isinstance(data, list) else []

    def describe_workspace(self, workspace_uuid: Optional[str] = None) -> dict:
        """从 list_workspaces 中找到指定 workspace，或返回第一个"""
        workspaces = self.list_workspaces()
        if not workspaces:
            return {"error": "未找到任何 workspace，请确认账号权限或先创建 workspace"}
        if workspace_uuid:
            for ws in workspaces:
                if ws.get("uuid") == workspace_uuid:
                    return ws
            return {"error": f"未找到 uuid={workspace_uuid} 的 workspace"}
        return workspaces[0]

    def get_workspace_url(self, workspace_uuid: Optional[str] = None,
                          branch_uuid: Optional[str] = None) -> Optional[str]:
        """获取 branch 连接 URL（优先从环境变量 AIBASE_BRANCH_URL，其次从 branch 的 domain 字段）"""
        if AIBASE_BRANCH_URL:
            return AIBASE_BRANCH_URL
        branch = self._get_default_branch(workspace_uuid, branch_uuid)
        return branch.get("domain") if branch else None

    def get_api_keys(self, workspace_uuid: Optional[str] = None,
                     branch_uuid: Optional[str] = None) -> list[dict]:
        """
        获取 branch 的 API Keys（anonKey / serviceRoleKey）。
        domain/anonKey/serviceRoleKey 均属于 branch，不属于 workspace。
        始终从管控面 branch 详情中获取，不再从环境变量读取。
        """
        keys = []
        try:
            branch = self._get_default_branch(workspace_uuid, branch_uuid)
            if branch:
                if branch.get("anonKey"):
                    keys.append({"type": "anon", "key": branch["anonKey"]})
                if branch.get("serviceRoleKey"):
                    keys.append({"type": "service_role", "key": branch["serviceRoleKey"]})
        except Exception as e:
            logger.error(f"管控面获取 branch key 失败：{e}")
        return keys

    def _get_default_branch(self, workspace_uuid: Optional[str] = None,
                             branch_uuid: Optional[str] = None) -> Optional[dict]:
        """
        获取目标 branch（优先指定 branch_uuid，其次取 defaultBranch=true 的分支，再取第一个）。
        workspace_uuid 为空时，先从 list_workspaces 取第一个 workspace。
        """
        try:
            if not workspace_uuid:
                workspaces = self.list_workspaces()
                if not workspaces:
                    return None
                # 取第一个 workspace（workspace 不含 domain，无法按 URL 匹配）
                ws = workspaces[0]
                workspace_uuid = ws.get("uuid")
            if not workspace_uuid:
                return None
            branches = self.list_branches(workspace_uuid)
            if not branches:
                return None
            if branch_uuid:
                for b in branches:
                    if b.get("uuid") == branch_uuid:
                        return b
                return None
            # 取 defaultBranch=true 的分支，否则取第一个
            for b in branches:
                if b.get("defaultBranch"):
                    return b
            return branches[0]
        except Exception as e:
            logger.warning(f"_get_default_branch 失败：{e}")
            return None

    def create_workspace(self, name: str, description: Optional[str] = None,
                         default_branch_name: Optional[str] = None,
                         default_branch_description: Optional[str] = None) -> dict:
        """POST /workspaces — 创建 workspace"""
        body: dict = {"name": name}
        if description is not None:
            body["description"] = description
        if default_branch_name is not None:
            body["defaultBranchName"] = default_branch_name
        if default_branch_description is not None:
            body["defaultBranchDescription"] = default_branch_description
        resp = self._fetch("POST", "/workspaces", body)
        _raise_if_error(resp)
        return resp.get("data") or {}

    def update_workspace(self, workspace_uuid: str, description: Optional[str] = None) -> None:
        """PUT /workspaces/{uuid} — 更新 workspace（当前支持描述）"""
        body: dict = {}
        if description is not None:
            body["description"] = description
        resp = self._fetch("PUT", f"/workspaces/{workspace_uuid}", body)
        _raise_if_error(resp)

    def delete_workspace(self, workspace_uuid: str) -> None:
        """DELETE /workspaces/{uuid} — 软删 workspace"""
        resp = self._fetch("DELETE", f"/workspaces/{workspace_uuid}")
        _raise_if_error(resp)

    # ── 成员管理接口 ──────────────────────────────────────────────────────────

    def list_members(self, workspace_uuid: str) -> list[dict]:
        """GET /workspaces/{uuid}/members"""
        resp = self._fetch("GET", f"/workspaces/{workspace_uuid}/members")
        _raise_if_error(resp)
        data = resp.get("data") or []
        return data if isinstance(data, list) else []

    def add_members(self, workspace_uuid: str, mis_list: list[str]) -> None:
        """POST /workspaces/{uuid}/members — 批量添加成员"""
        resp = self._fetch("POST", f"/workspaces/{workspace_uuid}/members", {"misList": mis_list})
        _raise_if_error(resp)

    def remove_members(self, workspace_uuid: str, mis_list: list[str]) -> None:
        """DELETE /workspaces/{uuid}/members — 批量删除成员"""
        resp = self._fetch("DELETE", f"/workspaces/{workspace_uuid}/members", {"misList": mis_list})
        _raise_if_error(resp)

    def replace_members(self, workspace_uuid: str, mis_list: list[str]) -> None:
        """PUT /workspaces/{uuid}/members — 全量覆盖成员"""
        resp = self._fetch("PUT", f"/workspaces/{workspace_uuid}/members", {"misList": mis_list})
        _raise_if_error(resp)

    # ── Branch 接口 ───────────────────────────────────────────────────────────

    def list_branches(self, workspace_uuid: str) -> list[dict]:
        """GET /workspaces/{uuid}/branches — 获取分支列表（默认分支优先）"""
        resp = self._fetch("GET", f"/workspaces/{workspace_uuid}/branches")
        _raise_if_error(resp)
        data = resp.get("data") or []
        return data if isinstance(data, list) else []

    def get_branch(self, workspace_uuid: str, branch_uuid: str) -> dict:
        """GET /workspaces/{uuid}/branches/{branchUuid} — 获取分支详情"""
        resp = self._fetch("GET", f"/workspaces/{workspace_uuid}/branches/{branch_uuid}")
        _raise_if_error(resp)
        return resp.get("data") or {}

    def create_branch(self, workspace_uuid: str, name: str,
                      description: Optional[str] = None,
                      parent_branch_uuid: Optional[str] = None) -> dict:
        """POST /workspaces/{uuid}/branches — 创建分支"""
        body: dict = {"name": name}
        if description is not None:
            body["description"] = description
        if parent_branch_uuid is not None:
            body["parentBranchUuid"] = parent_branch_uuid
        resp = self._fetch("POST", f"/workspaces/{workspace_uuid}/branches", body)
        _raise_if_error(resp)
        return resp.get("data") or {}

    def update_branch(self, workspace_uuid: str, branch_uuid: str,
                      description: Optional[str] = None) -> None:
        """PUT /workspaces/{uuid}/branches/{branchUuid} — 更新分支（当前支持描述）"""
        body: dict = {}
        if description is not None:
            body["description"] = description
        resp = self._fetch("PUT", f"/workspaces/{workspace_uuid}/branches/{branch_uuid}", body)
        _raise_if_error(resp)

    def delete_branch(self, workspace_uuid: str, branch_uuid: str) -> None:
        """DELETE /workspaces/{uuid}/branches/{branchUuid} — 删除分支"""
        resp = self._fetch("DELETE", f"/workspaces/{workspace_uuid}/branches/{branch_uuid}")
        _raise_if_error(resp)

    def set_default_branch(self, workspace_uuid: str, branch_uuid: str) -> None:
        """POST /workspaces/{uuid}/branches/{branchUuid}/set-default — 设置默认分支"""
        resp = self._fetch("POST", f"/workspaces/{workspace_uuid}/branches/{branch_uuid}/set-default")
        _raise_if_error(resp)

    def restart_branch(self, workspace_uuid: str, branch_uuid: str) -> None:
        """POST /workspaces/{uuid}/branches/{branchUuid}/restart — 异步重启分支实例"""
        resp = self._fetch("POST", f"/workspaces/{workspace_uuid}/branches/{branch_uuid}/restart")
        _raise_if_error(resp)



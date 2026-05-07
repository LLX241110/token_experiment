"""
WorkspaceTools：AI Base Workspace 管控操作
version: 0.4.0

管控面 API 通过 Python requests + yun_portal_ssoid Cookie 鉴权访问 MWS 网关。
SSO token 由 MOA 无感换票自动获取。

支持的操作：
  Workspace：
    list-workspaces       GET /workspaces
    describe-workspace    从列表中定位当前 workspace
    get-workspace-url     返回 workspace 访问 URL（从默认 branch 取 domain）
    get-keys              返回 API Keys（从默认 branch 取 anonKey/serviceRoleKey）
    create-workspace      POST /workspaces
    update-workspace      PUT /workspaces/{uuid}
    delete-workspace      DELETE /workspaces/{uuid}

  成员管理：
    list-members          GET /workspaces/{uuid}/members
    add-members           POST /workspaces/{uuid}/members
    remove-members        DELETE /workspaces/{uuid}/members
    replace-members       PUT /workspaces/{uuid}/members

  Branch 管理：
    list-branches         GET /workspaces/{uuid}/branches
    get-branch            GET /workspaces/{uuid}/branches/{branchUuid}
    create-branch         POST /workspaces/{uuid}/branches
    update-branch         PUT /workspaces/{uuid}/branches/{branchUuid}
    delete-branch         DELETE /workspaces/{uuid}/branches/{branchUuid}
    set-default-branch    POST /workspaces/{uuid}/branches/{branchUuid}/set-default
    restart-branch        POST /workspaces/{uuid}/branches/{branchUuid}/restart
"""
import logging
from typing import Optional
from .base import BaseTools, to_json, handle_errors, read_only_check

logger = logging.getLogger(__name__)


def _desync(coro):
    """将 async def 方法转为同步调用（aibase_client 现在是同步接口）。"""
    import asyncio
    import inspect
    if inspect.iscoroutine(coro):
        return asyncio.get_event_loop().run_until_complete(coro)
    return coro


class WorkspaceTools(BaseTools):

    def _mask_key(self, value: Optional[str], reveal: bool) -> Optional[str]:
        if value is None:
            return None
        if reveal:
            return value
        if len(value) <= 12:
            return "*" * len(value)
        return f"{value[:6]}...{value[-4:]}"

    @handle_errors
    async def list_workspaces(self) -> str:
        workspaces = self.aibase_client.list_workspaces()
        return to_json({
            "success": True,
            "workspaces": workspaces,
            "count": len(workspaces),
        })

    @handle_errors
    async def describe_workspace(self, workspace_uuid: Optional[str] = None) -> str:
        info = self.aibase_client.describe_workspace(workspace_uuid)
        return to_json({"success": True, "workspace": info})

    @handle_errors
    async def get_workspace_url(self, workspace_uuid: Optional[str] = None,
                                branch_uuid: Optional[str] = None) -> str:
        url = self.aibase_client.get_workspace_url(workspace_uuid, branch_uuid)
        if not url:
            return to_json({
                "success": False,
                "error": "无法获取 workspace URL，请先运行 list-branches 确认 branch 状态，"
                         "或设置 AIBASE_BRANCH_URL 环境变量（值为 branch.domain）",
            })
        return to_json({
            "success": True,
            "workspace_url": url,
        })

    @handle_errors
    async def get_keys(self, reveal: bool = False, workspace_uuid: Optional[str] = None,
                       branch_uuid: Optional[str] = None) -> str:
        keys = self.aibase_client.get_api_keys(workspace_uuid, branch_uuid)
        if not keys:
            return to_json({
                "success": False,
                "error": "无法获取 API Keys，请先运行 list-branches 确认 branch 状态为 RUNNING，"
                         "并传入正确的 --workspace-uuid 与 --branch-uuid",
            })
        masked = [
            {**k, "key": self._mask_key(k.get("key"), reveal)}
            for k in keys
        ]
        return to_json({
            "success": True,
            "reveal": reveal,
            "keys": masked,
        })

    @read_only_check
    @handle_errors
    async def create_workspace(self, name: str, description: Optional[str] = None,
                               default_branch_name: Optional[str] = None,
                               default_branch_description: Optional[str] = None) -> str:
        """创建新的 workspace"""
        if not name or not name.strip():
            return to_json({"success": False, "error": "workspace 名称不能为空"})
        ws = self.aibase_client.create_workspace(
            name.strip(), description, default_branch_name, default_branch_description
        )
        return to_json({
            "success": True,
            "message": f"workspace '{name}' 创建成功",
            "workspace": ws,
        })

    @read_only_check
    @handle_errors
    async def update_workspace(self, workspace_uuid: str, description: Optional[str] = None) -> str:
        """更新 workspace（当前支持描述）"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        self.aibase_client.update_workspace(workspace_uuid.strip(), description)
        return to_json({
            "success": True,
            "message": f"workspace '{workspace_uuid}' 已更新",
        })

    @read_only_check
    @handle_errors
    async def delete_workspace(self, workspace_uuid: str) -> str:
        """删除 workspace（软删）"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        self.aibase_client.delete_workspace(workspace_uuid.strip())
        return to_json({
            "success": True,
            "message": f"workspace '{workspace_uuid}' 已删除（软删）",
        })

    @handle_errors
    async def list_members(self, workspace_uuid: str) -> str:
        """获取 workspace 成员列表"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        members = self.aibase_client.list_members(workspace_uuid.strip())
        return to_json({
            "success": True,
            "members": members,
            "count": len(members),
        })

    @read_only_check
    @handle_errors
    async def add_members(self, workspace_uuid: str, mis_list: list[str]) -> str:
        """批量添加成员"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        if not mis_list:
            return to_json({"success": False, "error": "mis_list 不能为空"})
        self.aibase_client.add_members(workspace_uuid.strip(), mis_list)
        return to_json({
            "success": True,
            "message": f"已添加 {len(mis_list)} 位成员",
            "added": mis_list,
        })

    @read_only_check
    @handle_errors
    async def remove_members(self, workspace_uuid: str, mis_list: list[str]) -> str:
        """批量删除成员"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        if not mis_list:
            return to_json({"success": False, "error": "mis_list 不能为空"})
        self.aibase_client.remove_members(workspace_uuid.strip(), mis_list)
        return to_json({
            "success": True,
            "message": f"已移除 {len(mis_list)} 位成员",
            "removed": mis_list,
        })

    @read_only_check
    @handle_errors
    async def replace_members(self, workspace_uuid: str, mis_list: list[str]) -> str:
        """全量覆盖成员列表"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        self.aibase_client.replace_members(workspace_uuid.strip(), mis_list)
        return to_json({
            "success": True,
            "message": f"成员列表已更新，当前共 {len(mis_list)} 位成员",
            "members": mis_list,
        })

    # ── Branch 管理 ───────────────────────────────────────────────────────────

    @handle_errors
    async def list_branches(self, workspace_uuid: str) -> str:
        """获取 workspace 分支列表（默认分支优先）"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        branches = self.aibase_client.list_branches(workspace_uuid.strip())
        return to_json({
            "success": True,
            "branches": branches,
            "count": len(branches),
        })

    @handle_errors
    async def get_branch(self, workspace_uuid: str, branch_uuid: str) -> str:
        """获取 branch 详情（含 domain / anonKey / serviceRoleKey）"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        if not branch_uuid or not branch_uuid.strip():
            return to_json({"success": False, "error": "branch_uuid 不能为空"})
        branch = self.aibase_client.get_branch(workspace_uuid.strip(), branch_uuid.strip())
        return to_json({"success": True, "branch": branch})

    @read_only_check
    @handle_errors
    async def create_branch(self, workspace_uuid: str, name: str,
                            description: Optional[str] = None,
                            parent_branch_uuid: Optional[str] = None) -> str:
        """创建新分支（可基于父分支克隆）"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        if not name or not name.strip():
            return to_json({"success": False, "error": "分支名称（name）不能为空"})
        branch = self.aibase_client.create_branch(
            workspace_uuid.strip(), name.strip(), description, parent_branch_uuid
        )
        return to_json({
            "success": True,
            "message": f"分支 '{name}' 创建成功",
            "branch": branch,
        })

    @read_only_check
    @handle_errors
    async def update_branch(self, workspace_uuid: str, branch_uuid: str,
                            description: Optional[str] = None) -> str:
        """更新 branch（当前支持描述）"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        if not branch_uuid or not branch_uuid.strip():
            return to_json({"success": False, "error": "branch_uuid 不能为空"})
        self.aibase_client.update_branch(workspace_uuid.strip(), branch_uuid.strip(), description)
        return to_json({
            "success": True,
            "message": f"分支 '{branch_uuid}' 已更新",
        })

    @read_only_check
    @handle_errors
    async def delete_branch(self, workspace_uuid: str, branch_uuid: str) -> str:
        """删除 branch ⚠️ 不可逆，执行前须用户确认"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        if not branch_uuid or not branch_uuid.strip():
            return to_json({"success": False, "error": "branch_uuid 不能为空"})
        self.aibase_client.delete_branch(workspace_uuid.strip(), branch_uuid.strip())
        return to_json({
            "success": True,
            "message": f"分支 '{branch_uuid}' 已删除",
        })

    @read_only_check
    @handle_errors
    async def set_default_branch(self, workspace_uuid: str, branch_uuid: str) -> str:
        """设置默认分支"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        if not branch_uuid or not branch_uuid.strip():
            return to_json({"success": False, "error": "branch_uuid 不能为空"})
        self.aibase_client.set_default_branch(workspace_uuid.strip(), branch_uuid.strip())
        return to_json({
            "success": True,
            "message": f"已将分支 '{branch_uuid}' 设为默认分支",
        })

    @read_only_check
    @handle_errors
    async def restart_branch(self, workspace_uuid: str, branch_uuid: str) -> str:
        """异步重启 branch 对应的 Supabase 实例"""
        if not workspace_uuid or not workspace_uuid.strip():
            return to_json({"success": False, "error": "workspace_uuid 不能为空"})
        if not branch_uuid or not branch_uuid.strip():
            return to_json({"success": False, "error": "branch_uuid 不能为空"})
        self.aibase_client.restart_branch(workspace_uuid.strip(), branch_uuid.strip())
        return to_json({
            "success": True,
            "message": f"分支 '{branch_uuid}' 重启指令已发送（异步执行，请稍后通过 get-branch 确认状态）",
        })

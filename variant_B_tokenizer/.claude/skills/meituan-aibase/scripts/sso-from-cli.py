#!/usr/bin/env python3
"""
sso-from-cli.py — 通过 `sso` CLI 工具为 MWS 网关换票并注入到本地缓存

原理：
  美团 `sso` CLI（sso-auth-cli）能为任意 client_id 换发平台专属 ssoid。
  本脚本调用 `sso 60921859 --cookie`，解析返回的 `yun_portal_ssoid=<value>` 格式，
  写入本地 JSON 缓存文件 ~/.meituan_sso/aibase_sso.json，供 config.py 读取。

  MWS 网关（*.mws.sankuai.com）使用 yun_portal_ssoid Cookie 鉴权，
  对应 audience/client_id 为 60921859。

使用方式：
  python3 <skill_base_dir>/scripts/sso-from-cli.py            # 换票并注入
  python3 <skill_base_dir>/scripts/sso-from-cli.py --check    # 仅检查当前状态
  python3 <skill_base_dir>/scripts/sso-from-cli.py --dry-run  # 只换票不写入（预览）
"""

import json
import os
import shutil
import subprocess
import sys
import time

# ── 自重启：pyenv shim 在 CatDesk 环境下可能被 SIGKILL，用 execv 替换进程 ────
_SYS_PYTHON = "/usr/bin/python3"
_RESTARTED = os.environ.get("_SSO_AIBASE_RESTARTED") == "1"

if (
    not _RESTARTED
    and os.path.isfile(_SYS_PYTHON)
    and os.path.abspath(sys.executable) != os.path.abspath(_SYS_PYTHON)
):
    os.environ["_SSO_AIBASE_RESTARTED"] = "1"
    os.execv(_SYS_PYTHON, [_SYS_PYTHON, __file__] + sys.argv[1:])

# ── 平台配置 ──────────────────────────────────────────────────────────────────
# MWS 网关 client_id → cookie 名
CLIENT_ID = "60921859"
COOKIE_NAME = "yun_portal_ssoid"

# 本地缓存文件
SSO_CACHE_FILE = os.path.expanduser("~/.meituan_sso/aibase_sso.json")

# catclaw 沙箱 audience（mtsso-moa-local-exchange 用）
CATCLAW_AUDIENCE = CLIENT_ID


# ── 换票逻辑 ──────────────────────────────────────────────────────────────────

def _run_sso_command(cmd: list) -> "tuple[str, str] | None | str":
    """执行 sso 命令并解析输出。

    Returns:
        (cookie_name, cookie_value) 成功
        None                        普通失败
        "TIMEOUT"                   CIBA 等待超时
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=200,
        )
        output = result.stdout.strip()
        if result.returncode != 0 or not output:
            return None

        first_line = output.splitlines()[0]
        if "=" not in first_line:
            return None

        eq_idx = first_line.index("=")
        raw_key = first_line[:eq_idx]
        value = first_line[eq_idx + 1:]
        return raw_key, value

    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except (FileNotFoundError, OSError):
        return None


def fetch_token_via_sso_cli() -> "tuple[str, str] | None | str":
    """调用 `sso 60921859 --cookie` 获取 yun_portal_ssoid。

    若 `sso` 命令不存在或调用失败，自动降级使用
    `npx --yes --registry=http://r.npm.sankuai.com @dp/sso-auth-cli 60921859` 获取。

    Returns:
        (cookie_name, cookie_value) 成功
        None                        普通失败
        "TIMEOUT"                   CIBA 等待超时
    """
    sso_bin = shutil.which("sso")
    if sso_bin:
        result = _run_sso_command([sso_bin, CLIENT_ID, "--cookie"])
        if result is not None:
            return result

    npx_bin = shutil.which("npx")
    if npx_bin:
        return _run_sso_command(
            [npx_bin, "--yes", "--registry=http://r.npm.sankuai.com",
             "@dp/sso-auth-cli", CLIENT_ID],
        )

    return None


# ── catclaw 沙箱换票 ─────────────────────────────────────────────────────────

def _fetch_catclaw_token() -> str:
    """catclaw 沙箱：通过 npx mtsso-moa-local-exchange 获取 access_token。

    Returns:
        access_token 字符串。

    Raises:
        RuntimeError: npx 不在 PATH 或命令执行失败。
    """
    npx_bin = shutil.which("npx")
    if not npx_bin:
        raise RuntimeError(
            "未找到 `npx`，请确认 Node.js 已安装且 npx 在 PATH 中。\n"
            "安装方式：npm install @mtfe/mtsso-auth-official@latest --registry http://r.npm.sankuai.com"
        )

    cmd = [npx_bin, "mtsso-moa-local-exchange", "--audience", CATCLAW_AUDIENCE]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise RuntimeError("npx mtsso-moa-local-exchange 超时（>30s）")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"npx 执行失败: {exc}") from exc

    stdout = result.stdout.strip()
    if not stdout or result.returncode != 0:
        stderr_hint = result.stderr.strip()[:300] if result.stderr else ""
        raise RuntimeError(
            f"mtsso-moa-local-exchange 失败（exit={result.returncode}）"
            + (f"\nstderr: {stderr_hint}" if stderr_hint else "")
        )

    # 跳过 Warning 行，找第一个 JSON
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                payload = json.loads(line)
                token = payload.get("access_token", "")
                if token:
                    return token
            except json.JSONDecodeError:
                continue

    raise RuntimeError(f"mtsso-moa-local-exchange 输出中未找到 access_token: {stdout[:200]}")


# ── 缓存读写 ─────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if not os.path.exists(SSO_CACHE_FILE):
        return {}
    try:
        with open(SSO_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(data: dict) -> None:
    cache_dir = os.path.dirname(SSO_CACHE_FILE)
    os.makedirs(cache_dir, mode=0o700, exist_ok=True)
    with open(SSO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(SSO_CACHE_FILE, 0o600)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def check_status() -> None:
    """检查当前本地缓存中的 SSO token 状态"""
    cache = _load_cache()
    if not cache:
        print("[状态] 本地缓存中无 SSO token")
        return

    now = time.time()
    ck_name = cache.get("cookie_name", "?")
    ck_value = cache.get("cookie_value", "")
    obtained = cache.get("obtained_at", 0)
    source = cache.get("source", "?")
    age_min = (now - obtained) / 60 if obtained else -1

    print("[状态] 本地缓存中的 SSO token：")
    print(f"  cookie    : {ck_name}={ck_value[:16]}..." if ck_value else f"  cookie    : {ck_name}=(空)")
    print(f"  source    : {source}")
    print(f"  获取时间  : {age_min:.0f} 分钟前" if age_min >= 0 else "  获取时间  : 未知")

    # 默认 2 小时过期
    expires_in = cache.get("expires_in", 7200)
    elapsed = now - obtained if obtained else 999999
    if elapsed >= expires_in:
        print("  状态      : [X] 已过期")
    else:
        remaining = (expires_in - elapsed) / 60
        print(f"  状态      : [OK] 剩余 {remaining:.0f} 分钟")


def inject(dry_run: bool = False) -> None:
    """执行换票并注入到本地缓存"""

    # catclaw 沙箱环境
    if sys.platform == "linux" and os.path.isdir(os.path.expanduser("~/.openclaw")):
        print("[catclaw] 检测到沙箱环境，使用 mtsso-moa-local-exchange 获取 token...")
        try:
            token_value = _fetch_catclaw_token()
        except RuntimeError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
        ck_name = COOKIE_NAME
        source = "catclaw_npx_inject"
    else:
        # 正常环境：sso CLI 换票
        sso_bin = shutil.which("sso")
        npx_bin = shutil.which("npx")

        if sso_bin:
            print(f"[sso CLI] {sso_bin}")
        elif npx_bin:
            print(f"[sso CLI] sso 命令未找到，将使用 npx @dp/sso-auth-cli 替代（{npx_bin}）")
        else:
            print("[ERROR] 未找到 `sso` CLI 工具，且 npx 也不可用。")
            print()
            print("[AI-HINT] 请执行以下命令安装 sso CLI，安装完成后重新执行本脚本：")
            print("[AI-HINT]   npm install -g @dp/sso-auth-cli --registry http://r.npm.sankuai.com")
            sys.exit(1)

        print(f"[换票] 正在为 {CLIENT_ID} ({COOKIE_NAME}) 换票...")
        token = fetch_token_via_sso_cli()

        if token == "TIMEOUT":
            print("[ERROR] CIBA 授权超时（用户未在设备上确认授权）。")
            print("[AI-HINT] 请询问用户是否已在大象 App 上确认了登录授权请求。")
            sys.exit(1)

        if token is None:
            print("[ERROR] sso CLI 调用失败。")
            print("[AI-HINT] 请检查 sso CLI 是否已安装：which sso")
            print("[AI-HINT] 若未安装：npm install -g @dp/sso-auth-cli --registry http://r.npm.sankuai.com")
            sys.exit(1)

        ck_name, token_value = token
        if not token_value:
            print("[ERROR] sso CLI 返回了空值。")
            sys.exit(1)
        source = "sso_cli_inject"

    # 构建缓存数据
    now_ts = int(time.time())
    cache_data = {
        "cookie_name": ck_name,
        "cookie_value": token_value,
        "source": source,
        "obtained_at": now_ts,
        "expires_in": 7200,  # 默认 2 小时
    }

    print(f"\n[{'DRY-RUN 预览' if dry_run else '注入结果'}]")
    print(f"  [OK] {CLIENT_ID}")
    print(f"       cookie : {ck_name}={token_value[:16]}...")

    if dry_run:
        print("\n[DRY-RUN] 未写入缓存，去掉 --dry-run 后执行实际注入。")
        return

    _save_cache(cache_data)
    print(f"\n[完成] 已写入缓存：{SSO_CACHE_FILE}")


def main() -> None:
    check_only = "--check" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if check_only:
        check_status()
        return

    inject(dry_run=dry_run)


if __name__ == "__main__":
    main()

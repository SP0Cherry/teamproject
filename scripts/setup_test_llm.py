#!/usr/bin/env python3
"""测试用 LLM 配置脚本：把 SiliconFlow + deepseek-ai/DeepSeek-V4.1-Flash 写入 .env。

⚠️  测试专用，正式上线前：
      1. 运行 `python scripts/setup_test_llm.py --clear` 清空 .env 中的测试 LLM 配置；
      2. 删除本脚本文件（`scripts/setup_test_llm.py`），再换入正式配置。

安全约束（SEC-08 / OPS-02）：
  - 本脚本不包含任何真实密钥；仅硬编码非机密的 base_url 与 model 测试值。
  - API Key 通过 --api-key / 环境变量 SILICONFLOW_API_KEY(或 LLM_API_KEY) / 交互输入注入，
    只写入被 .gitignore 忽略的 .env，不会进入仓库、日志或镜像层。
  - 输出对密钥做脱敏（仅显示前 4 后 2 位），不打印完整 key。

用法：
  python scripts/setup_test_llm.py --check                 # 自动取 key 并验证连通性
  python scripts/setup_test_llm.py --api-key sk-xxx --check
  SILICONFLOW_API_KEY=sk-xxx python scripts/setup_test_llm.py --check
  python scripts/setup_test_llm.py --clear                 # 清空测试配置，恢复 demo 模式
"""

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 非机密测试配置：base_url 与 model 可硬编码；API Key 绝不硬编码。
TEST_BASE_URL = "https://api.siliconflow.cn/v1"
TEST_MODEL = "deepseek-ai/DeepSeek-V4.1-Flash"

# API Key 注入来源优先级：命令行 > 环境变量 > 交互输入
KEY_ENV_VARS = ("SILICONFLOW_API_KEY", "LLM_API_KEY")
TARGET_KEYS = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")


def find_env_file() -> Path:
    """脚本位于 <root>/scripts/，.env 位于项目根目录。"""
    return Path(__file__).resolve().parent.parent / ".env"


def read_env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def get_existing(lines: list[str], key: str) -> str:
    prefix = f"{key}="
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def upsert(lines: list[str], key: str, value: str) -> list[str]:
    """更新已存在的 KEY=value 行；不存在则追加。保留其余行与注释。"""
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.lstrip().startswith(prefix):
            lines[i] = f"{key}={value}"
            return lines
    lines.append(f"{key}={value}")
    return lines


def resolve_api_key(cli_key: str | None) -> str:
    if cli_key:
        return cli_key.strip()
    for var in KEY_ENV_VARS:
        val = os.environ.get(var, "").strip()
        if val:
            return val
    return getpass.getpass("SiliconFlow API Key（输入不回显）: ").strip()


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-2:]} (长度 {len(key)})"


def check_connectivity(base_url: str, key: str, model: str) -> tuple[bool, str]:
    """发一次最小 chat completion 验证连通性；不在异常信息里回显 key。"""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if resp.status == 200 and body.get("choices"):
            return True, f"HTTP {resp.status}"
        return False, f"HTTP {resp.status}: 响应缺少 choices"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="填入测试用 SiliconFlow LLM 配置到 .env（测试专用，上线前删除）"
    )
    parser.add_argument("--api-key", help="SiliconFlow API Key（优先；缺省读环境变量再交互输入）")
    parser.add_argument("--base-url", default=TEST_BASE_URL, help="默认测试值")
    parser.add_argument("--model", default=TEST_MODEL, help="默认测试值")
    parser.add_argument("--force", action="store_true", help="覆盖已有非空配置而不询问")
    parser.add_argument("--check", action="store_true", help="写入后调用模型验证连通性")
    parser.add_argument("--clear", action="store_true", help="清空 .env 中的 LLM_* 三项，恢复 demo 模式")
    args = parser.parse_args()

    env_path = find_env_file()
    lines = read_env_lines(env_path)

    if args.clear:
        for k in TARGET_KEYS:
            lines = upsert(lines, k, "")
        env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        print(f"[clear] 已清空 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL → {env_path}（恢复 demo 模式）")
        return

    existing_key = get_existing(lines, "LLM_API_KEY")
    if existing_key and not args.force:
        ans = input(".env 中已有 LLM_API_KEY，覆盖为测试 Key？[y/N] ").strip().lower()
        if ans != "y":
            print("已取消，未修改。")
            return

    key = resolve_api_key(args.api_key)
    if not key:
        print("错误：API Key 为空，未修改 .env。", file=sys.stderr)
        sys.exit(1)

    lines = upsert(lines, "LLM_BASE_URL", args.base_url)
    lines = upsert(lines, "LLM_API_KEY", key)
    lines = upsert(lines, "LLM_MODEL", args.model)
    env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    print(f"[ok] 已写入测试 LLM 配置 → {env_path}")
    print(f"     LLM_BASE_URL = {args.base_url}")
    print(f"     LLM_MODEL    = {args.model}")
    print(f"     LLM_API_KEY  = {mask_key(key)}")

    if args.check:
        print("[check] 正在验证模型连通性（仅打印状态，不回显密钥）...")
        ok, info = check_connectivity(args.base_url, key, args.model)
        print(f"[check] {'通过' if ok else '失败'}：{info}")
        if not ok:
            sys.exit(2)


if __name__ == "__main__":
    main()

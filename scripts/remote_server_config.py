"""Load remote SSH settings from scripts/server_config.json (env vars override)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import paramiko

_DEFAULT_ENV = "source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh"
_DEFAULT_CONFIG = Path(__file__).resolve().parent / "server_config.json"
_DEFAULT_PRIVATE_KEY = "~/.ssh/id_ed25519"


def config_path() -> Path:
    return Path(os.environ.get("APROF_SERVER_CONFIG", _DEFAULT_CONFIG))


def load_server_config() -> dict[str, str | int]:
    file_cfg: dict = {}
    path = config_path()
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            file_cfg = json.load(f)

    user = str(os.environ.get("APROF_REMOTE_USER") or file_cfg.get("user", ""))
    remote_root = str(os.environ.get("APROF_REMOTE_ROOT") or file_cfg.get("remote_root", ""))
    if not remote_root and user:
        remote_root = f"/home/{user}/aprof_fast_gelu_inject"

    return {
        "host": str(os.environ.get("APROF_REMOTE_HOST") or file_cfg.get("host", "")),
        "port": int(os.environ.get("APROF_REMOTE_PORT") or file_cfg.get("port", 22)),
        "user": user,
        "password": str(os.environ.get("APROF_REMOTE_PASS") or file_cfg.get("password", "")),
        "private_key": str(
            os.environ.get("APROF_REMOTE_PRIVATE_KEY")
            or file_cfg.get("private_key", _DEFAULT_PRIVATE_KEY)
        ),
        "private_key_passphrase": str(
            os.environ.get("APROF_REMOTE_PRIVATE_KEY_PASSPHRASE")
            or file_cfg.get("private_key_passphrase", "")
        ),
        "env": str(os.environ.get("APROF_REMOTE_ENV") or file_cfg.get("env", _DEFAULT_ENV)),
        "remote_root": remote_root,
        "asc_arch": str(os.environ.get("ASC_ARCH") or file_cfg.get("asc_arch", "dav-3510")),
        "inject_case": str(os.environ.get("INJECT_CASE") or file_cfg.get("inject_case", "inject_blockdim")),
    }


def require_server_config(cfg: dict[str, str | int]) -> None:
    missing = [k for k in ("host", "user") if not cfg.get(k)]
    if not cfg.get("password"):
        key_path = os.path.expanduser(str(cfg.get("private_key", _DEFAULT_PRIVATE_KEY)))
        if not os.path.isfile(key_path):
            missing.append(f"private_key（{key_path} 不存在）")
    if missing:
        raise SystemExit(
            f"缺少远程服务器配置: {', '.join(missing)}。"
            f"请填写 {config_path()}（可参考 server_config.example.json），"
            "或设置 APROF_REMOTE_* 环境变量。"
        )


def _load_private_key(path: str, passphrase: str) -> paramiko.PKey:
    pwd = passphrase or None
    for key_cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            return key_cls.from_private_key_file(path, password=pwd)
        except paramiko.SSHException:
            continue
    raise SystemExit(f"无法加载私钥: {path}")


def connect_ssh(cfg: dict[str, str | int]) -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    host = str(cfg["host"])
    port = int(cfg["port"])
    user = str(cfg["user"])
    password = str(cfg.get("password", ""))
    connect_kw: dict = {"hostname": host, "port": port, "username": user, "timeout": 60}

    if password:
        connect_kw["password"] = password
    else:
        key_path = os.path.expanduser(str(cfg.get("private_key", _DEFAULT_PRIVATE_KEY)))
        passphrase = str(cfg.get("private_key_passphrase", ""))
        if passphrase:
            connect_kw["pkey"] = _load_private_key(key_path, passphrase)
            connect_kw["allow_agent"] = False
            connect_kw["look_for_keys"] = False
        else:
            connect_kw["key_filename"] = key_path

    print(f"connecting {host}:{port} as {user}")
    ssh.connect(**connect_kw)
    return ssh

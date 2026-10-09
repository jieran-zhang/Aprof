"""Use the remote adapter shipped with the explicitly selected release."""
from pathlib import Path
import importlib.util
from aprof_layout import skill_lib
_spec = importlib.util.spec_from_file_location("aprof_remote_config", skill_lib() / "adapters/ascendc-remote-kernel-deploy/tools/remote_server_config.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
config_path = _module.config_path
load_server_config = _module.load_server_config
require_server_config = _module.require_server_config
connect_ssh = _module.connect_ssh

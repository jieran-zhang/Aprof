"""Task-local authenticated results, written only after an actual oracle pass.

The task owner is trusted to run code. This prevents accidental/unsigned receipt
promotion, not a malicious owner who can read the private key and replace runtime.
Loss of the volatile key invalidates all entries; independent audit bypasses them.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
from .execution_policy import task_root, local_path, append


class ValidationCache:
    def __init__(self, root):
        self.root = local_path(root) / "validation-cache"
        self.root.mkdir(mode=0o700, exist_ok=True)
        key = self.root / ".key"
        try:
            fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(os.urandom(32))
        if key.is_symlink() or key.stat().st_mode & 0o077:
            raise ValueError("validation key permissions/identity invalid")
        self.secret = key.read_bytes()
        if len(self.secret) != 32:
            raise ValueError("validation key invalid")

    def _signature(self, body):
        return hmac.new(self.secret, json.dumps(body, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()

    def get(self, key):
        path = self.root / (key.removeprefix("sha256:") + ".json")
        try:
            record = json.loads(path.read_text())
            body = record["body"]
            if body["key"] != key or not hmac.compare_digest(record["hmac"], self._signature(body)):
                return None
            if body["validation"]["returncode"] != 0 or body["validation"]["kind"] != "executed_oracle":
                return None
            return {"path": str(path), "sha256": "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(),
                    "validation": body["validation"]}
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put(self, key, validation):
        if validation.get("kind") != "executed_oracle" or validation.get("returncode") != 0:
            raise ValueError("only actual successful oracle execution can create cache entries")
        body = {"key": key, "validation": validation}
        target = self.root / (key.removeprefix("sha256:") + ".json")
        temporary = self.root / ("."+str(os.getpid())+".tmp")
        temporary.write_text(json.dumps({"body": body, "hmac": self._signature(body)}, sort_keys=True))
        os.replace(temporary, target)
        return self.get(key)


def cache_for(path):
    root = task_root(path)
    return ValidationCache(root) if root is not None else None

#!/usr/bin/env python3
"""只读校验新采集/学习记录；不执行记录内命令，不授予训练或发布资格。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

SCHEMAS = Path(__file__).resolve().parents[1] / "contracts"
OWNERS = ("diagnosis", "parallel-planning", "optimization")
PROTOCOL = "single_role_l2_clean_task_v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"重复 JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"非有限 JSON 数值: {value}")

    def number(value):
        parsed = float(value)
        require(math.isfinite(parsed), f"非有限 JSON 数值: {value}")
        return parsed

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid, parse_float=number)


def content_hash(value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def same_ref(left, right):
    return left is not None and right is not None and left["sha256"] == right["sha256"]


class Validator:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.checked = {}

    def path(self, relative):
        path = Path(relative)
        require(not path.is_absolute() and ".." not in path.parts,
                f"引用必须位于归档根下: {relative}")
        current = self.root
        for part in path.parts:
            current = current / part
            require(not current.is_symlink(), f"不接受 symlink: {relative}")
        require(current.is_file(), f"文件缺失: {relative}")
        return current

    def reference(self, ref):
        path = self.path(ref["path"])
        if path not in self.checked:
            self.checked[path] = file_hash(path)
        require(self.checked[path] == ref["sha256"], f"引用 hash 不匹配: {ref['path']}")
        return path

    def read(self, ref):
        try:
            return strict_json(self.reference(ref).read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(f"{ref['path']}: {error}") from error

    def references(self, value):
        if isinstance(value, dict):
            if set(value) == {"path", "sha256"}:
                self.reference(value)
            else:
                for item in value.values():
                    self.references(item)
        elif isinstance(value, list):
            for item in value:
                self.references(item)

    def shape(self, name, value):
        schema = strict_json((SCHEMAS / f"{name}.schema.json").read_text())
        Draft202012Validator(schema).validate(value)
        self.references(value)

    def batch(self, value):
        self.shape("optimization-batch", value)
        package = self.read(value["skill_lib_ref"])
        if package.get("schema_version") == "aprof.skill-lib-snapshot/v1":
            require(isinstance(package.get("files"), dict) and package["files"], "包快照缺少 files")
            for path, sha256 in package["files"].items():
                self.reference({"path": path, "sha256": sha256})
        membership = {}
        for split, ref in value["split_refs"].items():
            manifest = self.read(ref)
            members = manifest.get("active_operators")
            require(isinstance(members, list) and all(isinstance(x, str) for x in members),
                    "split manifest 缺少 active_operators")
            for operator in members:
                require(operator not in membership, "split 成员重复或跨 split")
                membership[operator] = split
        ids, operator_groups, group_splits, source_groups = set(), {}, {}, {}
        for task in value["tasks"]:
            require(task["task_id"] not in ids, "重复 task_id")
            ids.add(task["task_id"])
            op, group, split = task["operator"], task["group_id"], task["split"]
            require(membership.get(op) == split, "任务 split 与冻结清单不一致")
            require(operator_groups.setdefault(op, group) == group, "同算子拆成多个 group")
            require(group_splits.setdefault(group, split) == split, "同 group 跨 split")
            require(source_groups.setdefault(task["source_hash"], group) == group,
                    "同源 baseline 拆成多个 group")
        for owner in OWNERS:
            artifact = self.read(value["knowledge_refs"][owner])
            require(artifact.get("schema_version") == "aprof.knowledge/v1"
                    and artifact.get("owner") == owner and artifact.get("version"),
                    f"知识区身份错误: {owner}")
            if value["override_refs"][owner] is not None:
                override = self.read(value["override_refs"][owner])
                require(override.get("schema_version") == "aprof.knowledge-override/v1"
                        and override.get("base_hash") == content_hash(artifact)
                        and override.get("version") == artifact["version"],
                        "override 与知识区版本/hash 不一致")
        return value

    def task_result(self, value):
        self.shape("task-result", value)
        registered, closed = {}, {}
        lines = self.reference(value["journal_ref"]).read_text().splitlines()
        for seq, line in enumerate(lines, 1):
            event = strict_json(line)
            require(set(event) == {"seq", "event", "task_id", "attempt_id", "ref"}
                    and type(event["seq"]) is int and event["seq"] == seq
                    and event["task_id"] == value["task_id"]
                    and isinstance(event["attempt_id"], str) and event["attempt_id"],
                    "journal 字段、序号或任务身份错误")
            ref = event["ref"]
            require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "journal ref 错误")
            self.reference(ref)
            aid = event["attempt_id"]
            if event["event"] == "registered":
                require(aid not in registered, "候选重复登记")
                registered[aid] = ref
            elif event["event"] == "closed":
                require(aid in registered and aid not in closed, "候选未登记或重复闭合")
                closed[aid] = ref
            else:
                raise ValueError("未知 journal 事件")
        attempts = {a["attempt_id"]: a for a in value["attempts"]}
        require(len(attempts) == len(value["attempts"]) and set(attempts) == set(registered) == set(closed),
                "task-result 与 journal 候选集合不一致或仍未闭合")
        for aid, attempt in attempts.items():
            require(same_ref(attempt["terminal_ref"], closed[aid]), "task-result 不是 journal 的闭合结果")
        selected = value["selected_attempt_id"]
        require(selected is None or (selected in attempts and attempts[selected]["status"] == "completed"),
                "最终选择不是 completed 候选")
        return value

    def memory(self, value):
        self.shape("optimization-memory", value)
        batch = self.batch(self.read(value["batch_ref"]))
        tasks = {t["task_id"]: t for t in batch["tasks"]}
        require(value["task_id"] in tasks, "memory 的任务不在批次中")
        task = tasks[value["task_id"]]
        result = self.task_result(self.read(value["task_result_ref"]))
        require((result["batch_id"], result["task_id"], result["optimizer_id"])
                == (batch["batch_id"], task["task_id"], task["optimizer_id"]), "任务结果身份错配")
        require(value["recorder"]["agent_id"] != task["optimizer_id"], "recorder 必须独立于 optimizer")
        self.revision(value)
        declared = {a["attempt_id"]: a for a in result["attempts"]}
        attempts = {a["attempt_id"]: a for a in value["attempts"]}
        require(len(attempts) == len(value["attempts"]) and set(attempts) == set(declared),
                "memory 没有覆盖全部候选或有重复")
        seen, claim_ids = set(), set()
        for attempt in value["attempts"]:
            aid, parent = attempt["attempt_id"], attempt["parent_attempt_id"]
            require(attempt["status"] == declared[aid]["status"]
                    and same_ref(attempt["C5_ref"], declared[aid]["terminal_ref"]), "recorder 改写了闭合结果")
            require(parent is None or parent in seen, "父候选必须是此前的真实尝试")
            parent_hash = task["source_hash"] if parent is None else attempts[parent]["candidate_source_hash"]
            parent_ref = task["source_ref"] if parent is None else attempts[parent]["candidate_source_ref"]
            require(attempt["parent_source_hash"] == parent_hash
                    and same_ref(attempt["parent_source_ref"], parent_ref), "源码父本关联错误")
            seen.add(aid)
            require((attempt["candidate_source_ref"] is None) == (attempt["candidate_source_hash"] is None),
                    "候选源码引用与源码身份必须同时存在或为空")
            absent = any(x is None for x in attempt["handoffs"].values()) or attempt["timing_ref"] is None
            require(not absent or attempt["missing"], "缺阶段/计时必须记录 missing 原因")
            require(attempt["status"] not in ("failed", "blocked", "cancelled") or attempt["failure"],
                    "失败/阻塞/取消需记录原因")
            self.handoffs(attempt, task, batch)
            for observation in attempt["observations"]:
                require(observation["claim_id"] not in claim_ids, "重复 claim_id")
                claim_ids.add(observation["claim_id"])
        return task, batch

    def revision(self, value):
        current, seen = value, set()
        while current["previous_ref"] is not None:
            ref = current["previous_ref"]
            require(ref["sha256"] not in seen, "memory revision 成环")
            seen.add(ref["sha256"])
            previous = self.read(ref)
            self.shape("optimization-memory", previous)
            require(previous["memory_id"] == current["memory_id"]
                    and previous["task_id"] == current["task_id"]
                    and same_ref(previous["batch_ref"], current["batch_ref"])
                    and same_ref(previous["task_result_ref"], current["task_result_ref"])
                    and same_ref(previous["C0_ref"], current["C0_ref"])
                    and previous["revision"] + 1 == current["revision"], "memory revision 链错误")
            current = previous
        require(current["revision"] == 1, "首个 memory revision 必须为 1")

    def handoffs(self, attempt, task, batch):
        chain = []
        for stage, owner in zip(("C1", "C2", "C3"), OWNERS):
            ref = attempt["handoffs"][stage]
            if ref is None:
                chain.append(None)
                continue
            item = self.read(ref)
            require(item.get("schema_version") == "aprof.handoff/v2" and item.get("stage") == stage
                    and item.get("task_id") == task["task_id"]
                    and item.get("candidate_id") in (None, attempt["attempt_id"]), "handoff 身份错配")
            route = item.get("route", {})
            artifact = self.read(batch["knowledge_refs"][owner])
            override_ref = batch["override_refs"][owner]
            override_hash = content_hash(self.read(override_ref)) if override_ref else None
            require(route.get("owner") == owner and route.get("version") == artifact["version"]
                    and route.get("knowledge_hash") == content_hash(artifact)
                    and route.get("override_hash") == override_hash, "路由不是冻结的知识版本/参数")
            if chain:
                require(chain[-1] is not None and item.get("parent_hash") == content_hash(chain[-1]),
                        "C1→C2→C3 关联中断")
            chain.append(item)
        c1, c2, c3 = chain
        if c3:
            require(c3["candidate_id"] == attempt["attempt_id"]
                    and c3.get("implementation_source_hash") == attempt["candidate_source_hash"],
                    "C3 与真实候选源码身份不一致")
        if attempt["timing_ref"]:
            timing = self.read(attempt["timing_ref"])
            require(timing.get("kind") == "unified_timing_result"
                    and timing.get("protocol") == PROTOCOL
                    and timing.get("candidate_id") == attempt["attempt_id"], "计时身份或协议错误")
        if attempt["outcome_ref"]:
            require(all(chain) and attempt["timing_ref"], "缺完整链不能生成 knowledge-outcome")
            outcome = self.read(attempt["outcome_ref"])
            require(outcome.get("schema_version") == "aprof.knowledge-outcome/v1"
                    and outcome.get("task_id") == task["task_id"]
                    and outcome.get("candidate_id") == attempt["attempt_id"]
                    and outcome.get("handoff_hashes") == [content_hash(c) for c in chain]
                    and outcome.get("timing_result", {}).get("sha256") == attempt["timing_ref"]["sha256"]
                    and outcome.get("selected_actions") == c2.get("selected_actions")
                    and outcome.get("executed_actions") == c3.get("executed_actions")
                    and outcome.get("causal_claim") is False
                    and outcome.get("legacy_episode_eligible") is False, "knowledge-outcome 关联错误")

    def update(self, value):
        self.shape("knowledge-update", value)
        base = self.read(value["base_knowledge_ref"])
        require(base.get("schema_version") == "aprof.knowledge/v1" and base.get("owner") == value["owner"],
                "提案 base 知识区身份错误")
        candidate = self.read(value["candidate_artifact_ref"])
        policy = self.read(value["policy_ref"])
        require(policy.get("schema_version") == "aprof.learning-admission-policy/v1", "需要版本化的训练策略")
        if value["change_type"] == "parameters":
            require(set(candidate) == {"schema_version", "base_hash", "version", "parameters"}
                    and candidate["schema_version"] == "aprof.knowledge-override/v1"
                    and candidate["base_hash"] == content_hash(base) and candidate["version"] == base["version"],
                    "参数候选必须是绑定 base 的新 override")
            require(isinstance(candidate["parameters"], dict)
                    and set(candidate["parameters"]) == {c["target_id"] for c in value["changes"]},
                    "参数候选和逐项 changes 不一致")
        else:
            require(candidate.get("schema_version") == "aprof.knowledge/v1"
                    and candidate.get("owner") == value["owner"]
                    and candidate.get("version") != base.get("version"), "内容/结构修订必须生成新知识版本")
        memories, train_groups, train_ops = {}, set(), set()
        validation_groups, validation_ops = set(), set()
        train_sources, validation_sources, operator_groups = set(), set(), {}
        for expected, key in (("train", "training_memory_refs"), ("validation", "validation_memory_refs")):
            for ref in value[key]:
                memory = self.read(ref)
                task, batch = self.memory(memory)
                require(task["split"] == expected, "Teacher 不能用 validation/test 拟合")
                require(memory["memory_id"] not in memories, "重复 memory/revision 不能增加支持")
                require(operator_groups.setdefault(task["operator"], task["group_id"]) == task["group_id"],
                        "跨批次同算子拆成多个 group")
                memories[memory["memory_id"]] = memory
                if expected == "train":
                    require(same_ref(batch["knowledge_refs"][value["owner"]], value["base_knowledge_ref"])
                            and same_ref(batch["skill_lib_ref"], value["base_skill_lib_ref"]), "训练 memory 与 base 不一致")
                    train_groups.add(task["group_id"])
                    train_ops.add(task["operator"])
                    train_sources.add(task["source_hash"])
                else:
                    validation_groups.add(task["group_id"])
                    validation_ops.add(task["operator"])
                    validation_sources.add(task["source_hash"])
        require(not train_groups & validation_groups and not train_ops & validation_ops
                and not train_sources & validation_sources, "训练/验证 group 或源码泄漏")
        train_ids = {self.read(ref)["memory_id"] for ref in value["training_memory_refs"]}
        for change in value["changes"]:
            require(value["change_type"] != "parameters" or change["operation"] == "reweight",
                    "参数提案包含结构/内容操作")
            for signal in change["signals"]:
                require(signal["memory_id"] in train_ids, "更新信号不是 train memory")
                memory = memories[signal["memory_id"]]
                attempts = {a["attempt_id"]: a for a in memory["attempts"]}
                require(signal["attempt_id"] in attempts, "信号引用不存在的尝试")
                claims = {o["claim_id"] for o in attempts[signal["attempt_id"]]["observations"]
                          if o["owner"] == value["owner"]}
                require(set(signal["claim_ids"]) <= claims, "信号 claim 不存在或属于另一角色")
        if value["status"] == "validated_candidate":
            require(value["evaluation_ref"] is not None and value["validation_memory_refs"], "验证通过声明缺评估材料")
        return {"train_operator_groups": len(train_groups), "validation_operator_groups": len(validation_groups)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--kind", required=True, choices=("batch", "task-result", "memory", "update"))
    parser.add_argument("--input", required=True, help="相对 archive-root 的记录路径")
    args = parser.parse_args()
    try:
        validator = Validator(args.root)
        value = strict_json(validator.path(args.input).read_text(encoding="utf-8"))
        getattr(validator, args.kind.replace("-", "_"))(value)
        print(json.dumps({"integrity_valid": True, "kind": args.kind,
                          "checked_files": len(validator.checked), "promotion_authorized": False,
                          "runtime_replay_performed": False}, ensure_ascii=False))
    except (ValueError, ValidationError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"记录校验失败: {error}\n")


if __name__ == "__main__":
    main()

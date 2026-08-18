from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Iterable, Iterator

from .contracts import CandidateEpisode, EMPTY_ARTIFACT_SHA256, GateVerdict
from .errors import ContractError, StoreError
from .jsonio import canonical_json, content_hash, file_hash, require_sha256, to_primitive


_GENESIS_HASH = "sha256:" + "0" * 64

_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS artifacts (
    content_hash TEXT PRIMARY KEY CHECK(content_hash LIKE 'sha256:%'),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS artifact_locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT NOT NULL REFERENCES artifacts(content_hash),
    uri TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    media_type TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_hash, uri)
);
CREATE TABLE IF NOT EXISTS episodes (
    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    graph_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    selected_as_best INTEGER NOT NULL CHECK(selected_as_best IN (0, 1)),
    episode_hash TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS episodes_one_winner_per_session
ON episodes(session_id) WHERE selected_as_best = 1;
CREATE TABLE IF NOT EXISTS episode_artifacts (
    episode_id TEXT NOT NULL REFERENCES episodes(episode_id),
    role TEXT NOT NULL,
    content_hash TEXT NOT NULL REFERENCES artifacts(content_hash),
    PRIMARY KEY (episode_id, role)
);
CREATE TABLE IF NOT EXISTS episode_chain (
    sequence_id INTEGER PRIMARY KEY REFERENCES episodes(sequence_id),
    previous_chain_hash TEXT NOT NULL CHECK(previous_chain_hash LIKE 'sha256:%'),
    chain_hash TEXT NOT NULL UNIQUE CHECK(chain_hash LIKE 'sha256:%'),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TRIGGER IF NOT EXISTS episodes_no_update
BEFORE UPDATE ON episodes BEGIN SELECT RAISE(ABORT, 'episodes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS episodes_no_delete
BEFORE DELETE ON episodes BEGIN SELECT RAISE(ABORT, 'episodes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS artifacts_no_update
BEFORE UPDATE ON artifacts BEGIN SELECT RAISE(ABORT, 'artifacts are content-addressed and immutable'); END;
CREATE TRIGGER IF NOT EXISTS artifacts_no_delete
BEFORE DELETE ON artifacts BEGIN SELECT RAISE(ABORT, 'artifacts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS artifact_locations_no_update
BEFORE UPDATE ON artifact_locations BEGIN SELECT RAISE(ABORT, 'artifact locations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS artifact_locations_no_delete
BEFORE DELETE ON artifact_locations BEGIN SELECT RAISE(ABORT, 'artifact locations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS episode_artifacts_no_update
BEFORE UPDATE ON episode_artifacts BEGIN SELECT RAISE(ABORT, 'episode artifact links are append-only'); END;
CREATE TRIGGER IF NOT EXISTS episode_artifacts_no_delete
BEFORE DELETE ON episode_artifacts BEGIN SELECT RAISE(ABORT, 'episode artifact links are append-only'); END;
CREATE TRIGGER IF NOT EXISTS episode_chain_no_update
BEFORE UPDATE ON episode_chain BEGIN SELECT RAISE(ABORT, 'episode chain is append-only'); END;
CREATE TRIGGER IF NOT EXISTS episode_chain_no_delete
BEFORE DELETE ON episode_chain BEGIN SELECT RAISE(ABORT, 'episode chain is append-only'); END;
"""


def default_object_directory(store_path: str | Path) -> Path:
    """Return the deterministic CAS directory paired with a SQLite store."""

    path = Path(store_path)
    return path.parent / f"{path.name}.objects"


def _object_path(objects_path: Path, digest: str) -> Path:
    checked = require_sha256(digest, "content_hash")
    hexadecimal = checked.removeprefix("sha256:")
    return objects_path / "sha256" / hexadecimal[:2] / hexadecimal[2:]


def _chain_hash(sequence_id: int, episode_hash: str, previous_chain_hash: str) -> str:
    return content_hash({
        "sequence_id": sequence_id,
        "episode_hash": episode_hash,
        "previous_chain_hash": previous_chain_hash,
    })


def _artifact_links(episode: CandidateEpisode) -> dict[str, str]:
    """Enumerate typed artifact references in the complete authoritative batch."""

    links: dict[str, str] = {}
    evidence = {item.candidate_id: item for item in episode.gate_request.evidence}
    for draft in episode.gate_request.candidates:
        prefix = f"batch.{draft.candidate_id}"
        links[f"{prefix}.patch"] = draft.patch_artifact_hash
        links[f"{prefix}.source.baseline"] = draft.source_hashes.baseline
        links[f"{prefix}.source.candidate"] = draft.source_hashes.candidate
        for role, digest in evidence[draft.candidate_id].artifacts.items():
            links[f"{prefix}.evidence.{role}"] = digest
        for role, digest in {
            "model": draft.producer_hashes.model,
            "prompt": draft.producer_hashes.prompt,
            "agent": draft.producer_hashes.agent,
        }.items():
            if digest != "unknown":
                links[f"{prefix}.producer.{role}"] = digest
    return links


def _parse_payload(payload: str, path: str) -> CandidateEpisode:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise StoreError(f"{path}: invalid episode JSON: {exc}") from exc
    try:
        episode = CandidateEpisode.from_dict(value, path)
    except ContractError as exc:
        raise StoreError(f"{path}: authoritative episode validation failed: {exc}") from exc
    if canonical_json(episode) != payload:
        raise StoreError(f"{path}: payload is not canonical JSON")
    return episode


def _usage(episode: CandidateEpisode) -> dict[str, int]:
    return {
        "candidate_limit": 1,
        "build_limit": int(episode.evidence.build.value != "not_run"),
        "timing_limit": int(bool(
            episode.evidence.baseline_samples_ns or episode.evidence.candidate_samples_ns
        )),
        "full_profile_limit": int("profile_report" in episode.evidence.artifacts),
    }


def _enforce_cumulative_budgets(
    connection: sqlite3.Connection,
    incoming: Iterable[CandidateEpisode],
) -> None:
    by_session: dict[str, list[CandidateEpisode]] = {}
    pending = tuple(incoming)
    sessions = {item.draft.session_id for item in pending}
    if sessions:
        placeholders = ",".join("?" for _ in sessions)
        rows = connection.execute(
            f"SELECT payload_json FROM episodes WHERE session_id IN ({placeholders})",
            tuple(sorted(sessions)),
        )
        for index, (payload,) in enumerate(rows):
            episode = _parse_payload(str(payload), f"budget-existing[{index}]")
            by_session.setdefault(episode.draft.session_id, []).append(episode)
    for episode in pending:
        by_session.setdefault(episode.draft.session_id, []).append(episode)

    for session_id, episodes in by_session.items():
        budget_payloads = {canonical_json(item.context.budget) for item in episodes}
        if len(budget_payloads) != 1:
            raise StoreError(f"session {session_id!r} changed its immutable budget")
        totals = {name: 0 for name in _usage(episodes[0])}
        for episode in episodes:
            for name, count in _usage(episode).items():
                totals[name] += count
        budget = episodes[0].context.budget
        for name, used in totals.items():
            limit = budget.get(name)
            if limit is None:
                continue
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
                raise StoreError(f"context.budget.{name}: expected non-negative integer")
            if used > limit:
                raise StoreError(
                    f"session {session_id!r} exceeds {name}: used {used}, limit {limit}"
                )


def _require_complete_batches(episodes: Iterable[CandidateEpisode]) -> None:
    """Reject partial persistence of a gate batch.

    Winner selection and gate outcomes are batch-relative.  Storing only a
    favorable projection would therefore change the meaning of the trace.
    """

    groups: dict[str, tuple[set[str], list[str]]] = {}
    for episode in episodes:
        batch_id = content_hash({
            "context": episode.context,
            "gate_request": episode.gate_request,
            "finalized_at": episode.finalized_at,
            "runtime_build": episode.runtime_build,
        })
        expected = {item.candidate_id for item in episode.gate_request.candidates}
        if batch_id not in groups:
            groups[batch_id] = (expected, [])
        groups[batch_id][1].append(episode.draft.candidate_id)
    for batch_id, (expected, actual_list) in groups.items():
        actual = set(actual_list)
        if actual != expected or len(actual_list) != len(expected):
            raise StoreError(
                f"gate batch {batch_id} must be appended completely and exactly once; "
                f"expected={sorted(expected)}, actual={sorted(actual_list)}"
            )


def verify_store_connection(connection: sqlite3.Connection, objects_path: str | Path) -> None:
    """Verify payload attestations, CAS objects, links, and the append-only chain.

    This protects readers against accidental corruption and ordinary SQL writes.
    A process with administrative access to both the database and object directory
    remains outside the trust model; anchoring the returned head externally can be
    added when traces cross that trust boundary.
    """

    root = Path(objects_path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise StoreError(f"SQLite integrity check failed: {integrity!r}")
        rows = connection.execute(
            """SELECT e.sequence_id, e.episode_id, e.candidate_id, e.session_id,
                      e.task_id, e.graph_version, e.policy_version,
                      e.selected_as_best, e.episode_hash, e.payload_json,
                      c.previous_chain_hash, c.chain_hash
               FROM episodes AS e
               LEFT JOIN episode_chain AS c ON c.sequence_id = e.sequence_id
               ORDER BY e.sequence_id"""
        ).fetchall()
    except sqlite3.Error as exc:
        raise StoreError(f"could not verify episode store: {exc}") from exc

    previous = _GENESIS_HASH
    for expected_sequence, row in enumerate(rows, start=1):
        (
            sequence_id, episode_id, candidate_id, session_id, task_id,
            graph_version, policy_version, selected_as_best, stored_episode_hash,
            payload, previous_chain_hash, stored_chain_hash,
        ) = row
        if sequence_id != expected_sequence:
            raise StoreError(f"episode sequence is not contiguous at {sequence_id}")
        if previous_chain_hash is None or stored_chain_hash is None:
            raise StoreError(f"episode {episode_id} is missing its chain entry")
        episode = _parse_payload(str(payload), f"episode[{sequence_id}]")
        indexed = (
            episode.episode_id,
            episode.draft.candidate_id,
            episode.draft.session_id,
            episode.context.task_id,
            episode.draft.route.graph_version,
            episode.draft.route.policy_version,
            int(episode.outcome.selected_as_best),
            episode.episode_hash,
        )
        if indexed != (
            episode_id, candidate_id, session_id, task_id, graph_version,
            policy_version, selected_as_best, stored_episode_hash,
        ):
            raise StoreError(f"episode {episode_id} index columns do not match its payload")
        if previous_chain_hash != previous:
            raise StoreError(f"episode {episode_id} has a broken previous-chain link")
        expected_chain_hash = _chain_hash(sequence_id, stored_episode_hash, previous)
        if stored_chain_hash != expected_chain_hash:
            raise StoreError(f"episode {episode_id} has an invalid chain hash")

        expected_links = _artifact_links(episode)
        actual_links = dict(connection.execute(
            "SELECT role, content_hash FROM episode_artifacts WHERE episode_id=? ORDER BY role",
            (episode_id,),
        ))
        if actual_links != expected_links:
            raise StoreError(f"episode {episode_id} artifact links do not match its payload")
        for digest in sorted(set(expected_links.values())):
            object_path = _object_path(root, digest)
            if object_path.is_symlink() or not object_path.is_file():
                raise StoreError(f"CAS object is missing for {digest}")
            if file_hash(object_path) != digest:
                raise StoreError(f"CAS object content does not match {digest}")
        previous = stored_chain_hash

    chain_count = connection.execute("SELECT COUNT(*) FROM episode_chain").fetchone()[0]
    if chain_count != len(rows):
        raise StoreError("episode chain contains orphan entries")


class EpisodeStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.objects_path = default_object_directory(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.objects_path.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.executescript(_SCHEMA)
        self.connection.commit()

    def __enter__(self) -> "EpisodeStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def object_path(self, digest: str) -> Path:
        return _object_path(self.objects_path, digest)

    def register_artifact(
        self,
        path: str | Path,
        *,
        uri: str | None = None,
        media_type: str | None = None,
    ) -> str:
        """Copy a file into the immutable CAS and index its canonical location."""

        artifact_path = Path(path)
        if artifact_path.is_symlink() or not artifact_path.is_file():
            raise StoreError(f"artifact must be a regular non-symlink file: {artifact_path}")
        self.objects_path.mkdir(parents=True, exist_ok=True)
        temporary_fd, temporary_name = tempfile.mkstemp(prefix=".incoming-", dir=self.objects_path)
        temporary_path = Path(temporary_name)
        digest_builder = hashlib.sha256()
        try:
            with artifact_path.open("rb") as source, os.fdopen(temporary_fd, "wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest_builder.update(chunk)
                target.flush()
                os.fsync(target.fileno())
            digest = "sha256:" + digest_builder.hexdigest()
            # Re-read the completed copy.  The digest is never accepted solely
            # from the mutable source stream.
            if file_hash(temporary_path) != digest:
                raise StoreError("artifact copy failed its post-copy hash check")
            destination = self.object_path(digest)
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(temporary_path, destination)
            except FileExistsError:
                if destination.is_symlink() or not destination.is_file() or file_hash(destination) != digest:
                    raise StoreError(f"existing CAS object is corrupt: {digest}")
            finally:
                temporary_path.unlink(missing_ok=True)
            if file_hash(destination) != digest:
                raise StoreError(f"CAS object failed verification after installation: {digest}")

            size = destination.stat().st_size
            cas_uri = destination.resolve().as_uri()
            source_uri = uri or artifact_path.resolve().as_uri()
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                self.connection.execute(
                    "INSERT OR IGNORE INTO artifacts(content_hash) VALUES (?)", (digest,),
                )
                self.connection.execute(
                    "INSERT OR IGNORE INTO artifact_locations(content_hash, uri, size_bytes, media_type) VALUES (?, ?, ?, ?)",
                    (digest, cas_uri, size, media_type),
                )
                if source_uri != cas_uri:
                    self.connection.execute(
                        "INSERT OR IGNORE INTO artifact_locations(content_hash, uri, size_bytes, media_type) VALUES (?, ?, ?, ?)",
                        (digest, source_uri, size, media_type),
                    )
                self.connection.commit()
            except sqlite3.Error as exc:
                self.connection.rollback()
                raise StoreError(f"could not register artifact: {exc}") from exc
            return digest
        finally:
            try:
                os.close(temporary_fd)
            except OSError:
                pass
            temporary_path.unlink(missing_ok=True)

    def verify_artifact(self, digest: str) -> Path:
        destination = self.object_path(digest)
        if destination.is_symlink() or not destination.is_file():
            raise StoreError(f"CAS object is missing for {digest}")
        if file_hash(destination) != digest:
            raise StoreError(f"CAS object content does not match {digest}")
        row = self.connection.execute(
            "SELECT 1 FROM artifacts WHERE content_hash=?", (digest,),
        ).fetchone()
        if row is None:
            raise StoreError(f"CAS object is not indexed: {digest}")
        return destination

    def _validate_episode(self, value: CandidateEpisode) -> tuple[CandidateEpisode, str, dict[str, str]]:
        # Frozen dataclasses can be directly constructed.  A complete round-trip
        # forces nested invariants, the payload hash, and authoritative re-gating.
        try:
            episode = CandidateEpisode.from_dict(to_primitive(value))
        except ContractError as exc:
            raise StoreError(f"episode append rejected: {exc}") from exc
        payload = canonical_json(episode)
        links = _artifact_links(episode)
        for digest in sorted(set(links.values())):
            self.verify_artifact(digest)
        if episode.outcome.verdict is GateVerdict.VERIFIED_NOOP:
            baseline = self.verify_artifact(episode.draft.source_hashes.baseline)
            candidate = self.verify_artifact(episode.draft.source_hashes.candidate)
            patch = self.verify_artifact(episode.draft.patch_artifact_hash)
            if baseline != candidate:
                raise StoreError("verified NOOP baseline and candidate do not resolve to the same CAS object")
            if episode.draft.patch_artifact_hash != EMPTY_ARTIFACT_SHA256 or patch.stat().st_size != 0:
                raise StoreError("verified NOOP does not reference the canonical empty patch object")
        return episode, payload, links

    def append(self, episode: CandidateEpisode) -> int:
        return self.append_many((episode,))[0]

    def append_many(self, episodes: Iterable[CandidateEpisode]) -> tuple[int, ...]:
        """Validate and append a batch in one SQLite transaction."""

        validated = [self._validate_episode(item) for item in episodes]
        if not validated:
            return ()
        _require_complete_batches(episode for episode, _, _ in validated)
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            # Refuse to extend a store whose existing prefix is not already a
            # valid, fully materialized chain.  BEGIN IMMEDIATE prevents a
            # competing writer from changing that prefix before this commit.
            verify_store_connection(self.connection, self.objects_path)
            _enforce_cumulative_budgets(
                self.connection, (episode for episode, _, _ in validated)
            )
            previous_row = self.connection.execute(
                "SELECT chain_hash FROM episode_chain ORDER BY sequence_id DESC LIMIT 1"
            ).fetchone()
            previous = str(previous_row[0]) if previous_row is not None else _GENESIS_HASH
            sequences: list[int] = []
            for episode, payload, artifact_links in validated:
                # Re-hash while holding the write transaction so a corrupted CAS
                # is never knowingly committed after pre-validation.
                for digest in sorted(set(artifact_links.values())):
                    self.verify_artifact(digest)
                cursor = self.connection.execute(
                    """INSERT INTO episodes(
                        episode_id, candidate_id, session_id, task_id, graph_version,
                        policy_version, selected_as_best, episode_hash, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        episode.episode_id,
                        episode.draft.candidate_id,
                        episode.draft.session_id,
                        episode.context.task_id,
                        episode.draft.route.graph_version,
                        episode.draft.route.policy_version,
                        int(episode.outcome.selected_as_best),
                        episode.episode_hash,
                        payload,
                    ),
                )
                sequence_id = int(cursor.lastrowid)
                for role, digest in artifact_links.items():
                    self.connection.execute(
                        "INSERT INTO episode_artifacts(episode_id, role, content_hash) VALUES (?, ?, ?)",
                        (episode.episode_id, role, digest),
                    )
                current = _chain_hash(sequence_id, episode.episode_hash, previous)
                self.connection.execute(
                    "INSERT INTO episode_chain(sequence_id, previous_chain_hash, chain_hash) VALUES (?, ?, ?)",
                    (sequence_id, previous, current),
                )
                previous = current
                sequences.append(sequence_id)
            self.connection.commit()
            return tuple(sequences)
        except (sqlite3.Error, StoreError) as exc:
            self.connection.rollback()
            if isinstance(exc, StoreError):
                raise
            raise StoreError(f"episode append rejected: {exc}") from exc

    def verify_integrity(self) -> str:
        verify_store_connection(self.connection, self.objects_path)
        row = self.connection.execute(
            "SELECT chain_hash FROM episode_chain ORDER BY sequence_id DESC LIMIT 1"
        ).fetchone()
        return str(row[0]) if row is not None else _GENESIS_HASH

    def iter_payloads(self) -> Iterator[str]:
        self.verify_integrity()
        rows = self.connection.execute("SELECT payload_json FROM episodes ORDER BY sequence_id")
        for (payload,) in rows:
            yield str(payload)

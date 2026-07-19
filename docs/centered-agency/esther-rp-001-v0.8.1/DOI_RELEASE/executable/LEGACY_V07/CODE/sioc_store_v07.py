from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Mapping

from common_v07 import canonical_json
from formal_v07 import AuthorityDecision
from sioc_v07 import (
    CapabilityRecord,
    ControlRequest,
    EffectClass,
    EffectReceipt,
    OperationDescriptor,
    OperationRegistry,
    RequestRejected,
    validate_request,
    verify_authority_binding,
)


class SQLiteReferenceMonitor:
    """Durable reference projection for request/nonce/effect/receipt atomicity.

    This remains a local reference model, not a production actuator controller.
    Every execution uses one BEGIN IMMEDIATE transaction and one connection owner.
    """

    def __init__(self, path: str | Path, registry: OperationRegistry) -> None:
        self.path = Path(path)
        self.registry = registry
        self._initialize_schema()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    def _initialize_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS capabilities (
                    capability_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    principal TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    expiry_time INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    receipt_digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nonces (
                    capability_id TEXT NOT NULL,
                    capability_version INTEGER NOT NULL,
                    nonce TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    PRIMARY KEY (capability_id, capability_version, nonce)
                );
                CREATE TABLE IF NOT EXISTS effects (
                    effect_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    request_digest TEXT NOT NULL,
                    authority_decision_digest TEXT NOT NULL,
                    descriptor_digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    record TEXT NOT NULL
                );
                """
            )

    def initialize(self, capabilities: Iterable[CapabilityRecord], *, server_cut: int, server_time: int) -> None:
        caps = list(capabilities)
        for cap in caps:
            cap.validate()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('server_cut',?)", (str(server_cut),))
                conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('server_time',?)", (str(server_time),))
                conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('registry_digest',?)", (self.registry.digest,))
                for cap in caps:
                    conn.execute(
                        """INSERT OR REPLACE INTO capabilities
                           (capability_id,version,principal,scopes_json,active,expiry_time)
                           VALUES(?,?,?,?,?,?)""",
                        (
                            cap.capability_id,
                            cap.version,
                            cap.principal,
                            canonical_json(sorted(cap.scopes)),
                            1 if cap.active else 0,
                            cap.expiry_time,
                        ),
                    )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    @staticmethod
    def _receipt_to_json(receipt: EffectReceipt) -> str:
        return canonical_json(asdict(receipt))

    @staticmethod
    def _receipt_from_json(text: str) -> EffectReceipt:
        payload = json.loads(text)
        receipt = EffectReceipt(**payload)
        if not receipt.verify_digest():
            raise ValueError("stored receipt digest mismatch")
        return receipt

    @staticmethod
    def _mismatch_receipt(request: ControlRequest) -> EffectReceipt:
        return EffectReceipt.create(
            request=request,
            status="REQUEST_ID_MISMATCH",
            reason="REQUEST_ID_ALREADY_BOUND_TO_DIFFERENT_DIGEST",
            descriptor=None,
            effect_id=None,
            authority_decision_digest=None,
        )

    def _load_capabilities(self, conn: sqlite3.Connection) -> dict[str, CapabilityRecord]:
        rows = conn.execute(
            "SELECT capability_id,version,principal,scopes_json,active,expiry_time FROM capabilities"
        ).fetchall()
        return {
            row[0]: CapabilityRecord(
                capability_id=row[0],
                version=int(row[1]),
                principal=row[2],
                scopes=frozenset(json.loads(row[3])),
                active=bool(row[4]),
                expiry_time=int(row[5]),
            )
            for row in rows
        }

    def execute(self, request: ControlRequest, *, authority_decision: AuthorityDecision | None = None) -> EffectReceipt:
        digest = request.request_digest
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                prior = conn.execute(
                    "SELECT request_digest,receipt_json FROM requests WHERE request_id=?",
                    (request.context.request_id,),
                ).fetchone()
                if prior is not None:
                    if prior[0] == digest:
                        receipt = self._receipt_from_json(prior[1])
                    else:
                        receipt = self._mismatch_receipt(request)
                    conn.execute("COMMIT")
                    return receipt

                meta = dict(conn.execute("SELECT key,value FROM meta").fetchall())
                if meta.get("registry_digest") != self.registry.digest:
                    raise ValueError("registry digest mismatch")
                capabilities = self._load_capabilities(conn)
                descriptor: OperationDescriptor | None = None
                authority_digest: str | None = None
                try:
                    descriptor, _ = validate_request(
                        request,
                        capabilities=capabilities,
                        registry=self.registry,
                        server_cut=int(meta["server_cut"]),
                        server_time=int(meta["server_time"]),
                    )
                    authority_digest = verify_authority_binding(request, descriptor, authority_decision)
                    nonce_exists = conn.execute(
                        """SELECT 1 FROM nonces
                           WHERE capability_id=? AND capability_version=? AND nonce=?""",
                        (
                            request.context.capability_id,
                            request.context.capability_version,
                            request.context.nonce,
                        ),
                    ).fetchone()
                    if nonce_exists:
                        raise RequestRejected("NONCE_REPLAY")
                except RequestRejected as exc:
                    receipt = EffectReceipt.create(
                        request=request,
                        status="REJECTED",
                        reason=exc.reason,
                        descriptor=descriptor,
                        effect_id=None,
                        authority_decision_digest=authority_digest,
                    )
                    conn.execute(
                        "INSERT INTO requests(request_id,request_digest,receipt_json,receipt_digest) VALUES(?,?,?,?)",
                        (request.context.request_id, digest, self._receipt_to_json(receipt), receipt.receipt_digest),
                    )
                    conn.execute("INSERT INTO audit(record) VALUES(?)", (f"Rejected:{receipt.receipt_digest}",))
                    conn.execute("COMMIT")
                    return receipt

                assert descriptor is not None
                effect_id = None if descriptor.effect_class is EffectClass.NONE else request.expected_effect_id
                receipt = EffectReceipt.create(
                    request=request,
                    status="OBSERVED" if descriptor.effect_class is EffectClass.NONE else "APPLIED",
                    reason=None,
                    descriptor=descriptor,
                    effect_id=effect_id,
                    authority_decision_digest=authority_digest,
                )
                conn.execute(
                    "INSERT INTO nonces(capability_id,capability_version,nonce,request_id) VALUES(?,?,?,?)",
                    (
                        request.context.capability_id,
                        request.context.capability_version,
                        request.context.nonce,
                        request.context.request_id,
                    ),
                )
                if effect_id is not None:
                    assert authority_digest is not None
                    conn.execute(
                        """INSERT INTO effects(effect_id,request_id,request_digest,authority_decision_digest,descriptor_digest)
                           VALUES(?,?,?,?,?)""",
                        (effect_id, request.context.request_id, digest, authority_digest, descriptor.descriptor_digest),
                    )
                conn.execute(
                    "INSERT INTO requests(request_id,request_digest,receipt_json,receipt_digest) VALUES(?,?,?,?)",
                    (request.context.request_id, digest, self._receipt_to_json(receipt), receipt.receipt_digest),
                )
                conn.execute("INSERT INTO audit(record) VALUES(?)", (f"Committed:{receipt.receipt_digest}",))
                conn.execute("COMMIT")
                return receipt
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK")
                # A concurrent transaction may have won. Re-read the canonical request result.
                with self._connection() as read_conn:
                    prior = read_conn.execute(
                        "SELECT request_digest,receipt_json FROM requests WHERE request_id=?",
                        (request.context.request_id,),
                    ).fetchone()
                    if prior is not None:
                        if prior[0] == digest:
                            return self._receipt_from_json(prior[1])
                        return self._mismatch_receipt(request)
                # Same nonce under a different request becomes a durable rejection for this request.
                with self._connection() as write_conn:
                    write_conn.execute("BEGIN IMMEDIATE")
                    try:
                        prior = write_conn.execute(
                            "SELECT request_digest,receipt_json FROM requests WHERE request_id=?",
                            (request.context.request_id,),
                        ).fetchone()
                        if prior is not None:
                            write_conn.execute("COMMIT")
                            return self._receipt_from_json(prior[1]) if prior[0] == digest else self._mismatch_receipt(request)
                        receipt = EffectReceipt.create(
                            request=request,
                            status="REJECTED",
                            reason="NONCE_REPLAY",
                            descriptor=None,
                            effect_id=None,
                            authority_decision_digest=None,
                        )
                        write_conn.execute(
                            "INSERT INTO requests(request_id,request_digest,receipt_json,receipt_digest) VALUES(?,?,?,?)",
                            (request.context.request_id, digest, self._receipt_to_json(receipt), receipt.receipt_digest),
                        )
                        write_conn.execute("INSERT INTO audit(record) VALUES(?)", (f"Rejected:{receipt.receipt_digest}",))
                        write_conn.execute("COMMIT")
                        return receipt
                    except Exception:
                        write_conn.execute("ROLLBACK")
                        raise
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def counts(self) -> dict[str, int]:
        with self._connection() as conn:
            return {
                "requests": conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0],
                "nonces": conn.execute("SELECT COUNT(*) FROM nonces").fetchone()[0],
                "effects": conn.execute("SELECT COUNT(*) FROM effects").fetchone()[0],
                "audit": conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0],
            }

    def receipt(self, request_id: str) -> EffectReceipt:
        with self._connection() as conn:
            row = conn.execute("SELECT receipt_json FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                raise KeyError(request_id)
            return self._receipt_from_json(row[0])

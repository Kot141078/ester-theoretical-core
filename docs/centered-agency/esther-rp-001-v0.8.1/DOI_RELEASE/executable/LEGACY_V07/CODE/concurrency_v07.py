from __future__ import annotations

import json
import multiprocessing as mp
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from formal_v07 import AuthorityCutLedger, AuthorityEvent, AuthorityEventKind
from sioc_store_v07 import SQLiteReferenceMonitor
from sioc_v07 import CapabilityRecord, ControlRequest, InvocationContext, default_registry


def _capability() -> CapabilityRecord:
    return CapabilityRecord("cap", 1, "agent", frozenset({"actuate"}), True, 10)


def _request(request_id: str, nonce: str) -> ControlRequest:
    return ControlRequest(
        InvocationContext("agent", "cap", 1, "actuate", nonce, request_id, 2),
        "ACTUATE",
        "target",
        "actuator:generic",
        "v1",
    )


def _decision(req: ControlRequest):
    ledger = AuthorityCutLedger(start_cut=2)
    return ledger.commit_cut(
        2,
        (
            AuthorityEvent(
                f"event:{req.context.request_id}",
                AuthorityEventKind.INVOCATION,
                "cap",
                1,
                2,
                req.context.request_id,
                req.request_digest,
                req.expected_effect_id,
            ),
        ),
    )[0]


def _process_worker(db_path: str, request_id: str, nonce: str, queue) -> None:
    store = SQLiteReferenceMonitor(db_path, default_registry())
    req = _request(request_id, nonce)
    try:
        receipt = store.execute(req, authority_decision=_decision(req))
        queue.put(("OK", receipt.status, receipt.reason))
    except Exception as exc:  # recorded as infrastructure failure, never success
        queue.put(("ERROR", type(exc).__name__, str(exc)))


def run_concurrency(*, thread_rounds: int = 100, process_rounds: int = 20) -> dict:
    thread_failures = []
    process_failures = []
    with tempfile.TemporaryDirectory(prefix="esther-v07-concurrency-") as td:
        root = Path(td)
        for round_index in range(thread_rounds):
            db = root / f"thread-{round_index}.sqlite3"
            store = SQLiteReferenceMonitor(db, default_registry())
            store.initialize([_capability()], server_cut=2, server_time=2)

            def worker(i: int) -> str:
                req = _request(f"t{round_index}-{i}", f"nonce-{round_index}")
                return store.execute(req, authority_decision=_decision(req)).status

            with ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(worker, range(8)))
            counts = store.counts()
            if statuses.count("APPLIED") != 1 or statuses.count("REJECTED") != 7 or counts["effects"] != 1 or counts["nonces"] != 1:
                thread_failures.append({"round": round_index, "statuses": statuses, "counts": counts})

        # fork is used where available; spawn remains compatible with the top-level worker.
        methods = mp.get_all_start_methods()
        method = "fork" if "fork" in methods else "spawn"
        ctx = mp.get_context(method)
        for round_index in range(process_rounds):
            db = root / f"process-{round_index}.sqlite3"
            store = SQLiteReferenceMonitor(db, default_registry())
            store.initialize([_capability()], server_cut=2, server_time=2)
            queue = ctx.Queue()
            processes = [
                ctx.Process(target=_process_worker, args=(str(db), f"p{round_index}-{i}", f"nonce-p-{round_index}", queue))
                for i in range(4)
            ]
            for process in processes:
                process.start()
            results = [queue.get(timeout=30) for _ in processes]
            for process in processes:
                process.join(timeout=30)
            counts = store.counts()
            statuses = [r[1] for r in results if r[0] == "OK"]
            errors = [r for r in results if r[0] == "ERROR"]
            if errors or statuses.count("APPLIED") != 1 or statuses.count("REJECTED") != 3 or counts["effects"] != 1 or counts["nonces"] != 1:
                process_failures.append({"round": round_index, "results": results, "counts": counts})

    return {
        "thread_rounds": thread_rounds,
        "process_rounds": process_rounds,
        "thread_failures": thread_failures,
        "process_failures": process_failures,
        "pass": not thread_failures and not process_failures,
    }


if __name__ == "__main__":
    report = run_concurrency()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["pass"] else 1)

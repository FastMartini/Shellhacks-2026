"""db.get() under FastAPI's threadpool: sync routes read the ledger from many threads while the vault writes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from app import config, db, ledger

W = "SofiaWallet111"


@pytest.fixture
def file_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    db.use(None)
    yield
    db.use(None)


def test_concurrent_reads_and_writes_do_not_error(file_db):
    ts = datetime(2026, 9, 25, 9, 31, tzinfo=config.ET)

    def write(i):
        ledger.record(W, "deposit", None, None, None, 1_000_000 + i, ts, f"sig{i}")

    def read(_):
        return len(ledger.rows(W))

    with ThreadPoolExecutor(max_workers=16) as pool:
        jobs = [pool.submit(write if i % 4 == 0 else read, i) for i in range(800)]
        for j in jobs:
            j.result()  # re-raises sqlite3.InterfaceError / ProgrammingError from a shared connection

    assert len(ledger.rows(W)) == 200


def test_each_thread_gets_its_own_connection(file_db):
    with ThreadPoolExecutor(max_workers=1) as pool:
        other = pool.submit(db.get).result()
    assert other is not db.get()
    assert db.get() is db.get()


def test_use_pins_one_connection_for_every_thread(file_db):
    c = db.connect(":memory:")
    db.use(c)
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(db.get).result() is c

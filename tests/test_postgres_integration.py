"""Real PostgreSQL tests: opt in with TWINFORGE_TEST_DATABASE_URL.

Only a generated schema is created/dropped; never use a production database.
"""
import os
import unittest
import uuid
from urllib.parse import urlsplit
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import asyncpg
from app.storage.postgres import PostgresStore, PersistenceError
from app.services.sync_service import SyncService
from app.twin.mapper import simulator_asset_to_twin
from app.twin.registry import TwinRegistry
from test_source_connectivity import make_asset, connection_error


@unittest.skipUnless(os.getenv("TWINFORGE_TEST_DATABASE_URL"), "No isolated PostgreSQL test URL configured")
class PostgresIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dsn = os.environ["TWINFORGE_TEST_DATABASE_URL"]
        if urlsplit(self.dsn).path != "/twinforge_test":
            raise RuntimeError("Integration tests require a dedicated database named twinforge_test")
        self.schema = "tf_test_" + uuid.uuid4().hex
        self.admin = await asyncpg.connect(self.dsn, timeout=5)
        if await self.admin.fetchval("SELECT current_database()") != "twinforge_test":
            await self.admin.close()
            raise RuntimeError("Refusing to modify a non-test database")
        await self.admin.execute(f'CREATE SCHEMA "{self.schema}"')
        self.store = await self.new_store()
        await self.store.migrate()

    async def new_store(self):
        store = PostgresStore(self.dsn)
        store._pool = await asyncpg.create_pool(self.dsn, min_size=0, max_size=2,
            timeout=5, command_timeout=5, server_settings={"search_path": self.schema})
        return store

    async def asyncTearDown(self):
        await self.store.close()
        await self.admin.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        await self.admin.close()

    async def save(self, seq=1, run="run-1", state="RUNNING", fault=None, values=None):
        asset = make_asset(sequence=seq)
        asset["dynamic_state"]["state"] = state
        asset["dynamic_state"]["active_fault"] = fault
        if values is not None:
            asset["dynamic_state"]["values"] = values
        await self.store.save(run, [simulator_asset_to_twin(asset)], datetime.now(timezone.utc))

    async def test_identity_and_telemetry_round_trip(self):
        await self.save()
        rows = await self.store.history("CNC_01", "telemetry")
        self.assertEqual(rows[0]["telemetry_values"], {"temperature": 42.0})
        self.assertTrue(rows[0]["valid"])
        self.assertIsNotNone(rows[0]["observed_at"].tzinfo)
        async with self.store.connection() as conn:
            identity = await conn.fetchrow("SELECT * FROM assets")
            self.assertEqual(identity["factory_id"], "FACTORY_01")
            self.assertEqual(identity["line_id"], "LINE_01")
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM factories"), 1)

    async def test_transitions_fault_recovery_and_unchanged_state(self):
        await self.save(1)
        await self.save(2)
        await self.save(3, state="FAULT", fault="OVERHEAT")
        await self.save(4)
        rows = await self.store.history("CNC_01", "history")
        self.assertEqual([r["kind"] for r in rows], ["state_observed", "state_changed", "fault_started", "state_changed", "fault_recovered"])

    async def test_duplicate_lower_sequence_and_new_run(self):
        await self.save(10)
        await self.save(10)
        await self.save(9)
        await self.save(0, run="run-2")
        rows = await self.store.history("CNC_01", "telemetry")
        self.assertEqual([r["sequence"] for r in rows], [10, 0])
        self.assertEqual(len(await self.store.history("CNC_01", "history")), 2)

    async def test_missing_invalid_quality_and_zero_are_distinct(self):
        asset = make_asset()
        asset["dynamic_state"]["values"] = None
        asset["dynamic_state"]["last_telemetry_timestamp"] = "bad-time"
        asset["data_quality"].update(valid=False, fresh=False, reason="no telemetry")
        await self.store.save("run-1", [simulator_asset_to_twin(asset)], datetime.now(timezone.utc))
        await self.save(2, values={"temperature": 0})
        rows = await self.store.history("CNC_01", "telemetry")
        self.assertIsNone(rows[0]["telemetry_values"])
        self.assertIsNone(rows[0]["source_timestamp"])
        self.assertEqual(rows[0]["raw_source_timestamp"], "bad-time")
        self.assertFalse(rows[0]["valid"])
        self.assertEqual(rows[1]["telemetry_values"]["temperature"], 0)

    async def test_restart_migrations_and_pagination(self):
        await self.save(1)
        await self.save(2)
        await self.store.close()
        self.store = await self.new_store()
        await self.store.migrate()
        await self.save(2)
        first = await self.store.history("CNC_01", "telemetry", limit=1)
        rest = await self.store.history("CNC_01", "telemetry", after_id=first[0]["id"])
        self.assertEqual([r["sequence"] for r in first + rest], [1, 2])
        self.assertEqual(await self.store.history("missing", "history"), [])

    async def test_failed_batch_rolls_back_and_history_survives_disconnect(self):
        await self.save(1)
        invalid = simulator_asset_to_twin(make_asset(sequence=-1))
        valid = simulator_asset_to_twin(make_asset(asset_id="ROLLBACK_ONLY", sequence=1))
        with self.assertRaises(PersistenceError):
            await self.store.save("run-2", [valid, invalid], datetime.now(timezone.utc))
        async with self.store.connection() as conn:
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM source_runs"), 1)
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM observations"), 1)
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM assets WHERE asset_id='ROLLBACK_ONLY'"), 0)
        service = SyncService(TwinRegistry(), AsyncMock(side_effect=connection_error()), store=self.store)
        with self.assertRaises(Exception):
            await service.sync_once()
        self.assertEqual(len(await self.store.history("CNC_01", "telemetry")), 1)

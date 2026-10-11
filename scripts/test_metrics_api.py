import asyncio
import aiosqlite
from backend.services.metrics_service import build_metrics

async def run():
    async with aiosqlite.connect('noc_automation_4.db') as conn:
        conn.row_factory = aiosqlite.Row
        print("--- 24h Metrics ---")
        metrics = await build_metrics(conn, "24h")
        print(f"Total: {metrics['total_events']}")
        print(f"Top Devices: {metrics['top_alerting_devices'][:2]}")
        
        print("\n--- 30d Metrics ---")
        metrics = await build_metrics(conn, "30d")
        print(f"Total: {metrics['total_events']}")
        print(f"Vendors: {metrics['events_by_vendor']}")
        print(f"Severities: {metrics['events_by_severity']}")

if __name__ == "__main__":
    asyncio.run(run())

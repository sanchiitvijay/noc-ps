import asyncio
import aiosqlite
from backend.services.metrics_service import build_metrics

async def main():
    async with aiosqlite.connect("noc_automation_4.db") as conn:
        conn.row_factory = aiosqlite.Row
        metrics_24h = await build_metrics(conn, "24h")
        print(f"24h trend length: {len(metrics_24h['events_trend'])}")
        metrics_7d = await build_metrics(conn, "7d")
        print(f"7d trend length: {len(metrics_7d['events_trend'])}")
        metrics_30d = await build_metrics(conn, "30d")
        print(f"30d trend length: {len(metrics_30d['events_trend'])}")
        
if __name__ == "__main__":
    asyncio.run(main())

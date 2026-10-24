import httpx

SIMULATOR_URL = "http://127.0.0.1:8000"


async def get_snapshot():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SIMULATOR_URL}/api/v1/snapshot"
        )

        response.raise_for_status()

        return response.json()
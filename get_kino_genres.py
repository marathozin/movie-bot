import httpx
import asyncio
from pprint import pprint


async def get_kinopoisk_genres(api_key: str):
    url = "https://kinopoiskapiunofficial.tech/api/v2.2/films/collections"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url, headers=headers, params={"type": "TOP_POPULAR_MOVIES", "page": 1}
        )
        response.raise_for_status()
        data = response.json()

        films = data.get("items", [])

        for film in films:
            pprint(film)


if __name__ == "__main__":
    API_KEY = ""
    asyncio.run(get_kinopoisk_genres(API_KEY))

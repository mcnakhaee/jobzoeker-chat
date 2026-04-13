import os
import weaviate
from weaviate.classes.query import Filter

COLLECTION_NAME = "libra_job_search"
VECTOR_NAME = "description_vector"

_client: weaviate.WeaviateAsyncClient | None = None


async def get_client() -> weaviate.WeaviateAsyncClient:
    global _client
    if _client is None:
        headers = {"X-Mistral-Api-Key": os.environ["MISTRAL_API_KEY"]}
        api_key = os.getenv("WEAVIATE_API_KEY")

        if api_key:
            _client = weaviate.use_async_with_weaviate_cloud(
                cluster_url=os.environ["WEAVIATE_URL"],
                auth_credentials=weaviate.auth.AuthApiKey(api_key),
                headers=headers,
            )
        else:
            _client = weaviate.use_async_with_local(headers=headers)

        await _client.connect()

    return _client


async def search_jobs(query: str, top_k: int = 7, location: str | None = None) -> list[dict]:
    client = await get_client()
    location_filter = Filter.by_property("location").like(f"*{location}*") if location else None
    response = await client.collections.get(COLLECTION_NAME).query.near_text(
        query=query,
        target_vector=VECTOR_NAME,
        limit=top_k,
        filters=location_filter,
        return_properties=["title", "company", "location", "description", "uuid"],
    )
    return [
        {
            "title":       obj.properties.get("title", ""),
            "company":     obj.properties.get("company", ""),
            "location":    obj.properties.get("location", ""),
            "description": (obj.properties.get("description") or "")[:300],
            "uuid":        obj.properties.get("uuid", ""),
        }
        for obj in response.objects
    ]


async def close() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None

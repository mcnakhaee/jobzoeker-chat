"""
One-time script to create the Weaviate collection and insert job listings from CSV.

Run once before starting the server:
    python -m data.index_jobs

The collection schema mirrors the definition used in the notebook:
  - Properties : title, company, location, description, uuid
  - Vectorizer : text2vec_mistral on `description` → stored as `description_vector`

Vectorization happens inside Weaviate on insert — no local embedding step needed.
"""

import os
import uuid
import pandas as pd
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "libra_job_search"


def create_collection(client: weaviate.WeaviateClient) -> None:
    """Drop and recreate the collection — idempotent, safe to re-run."""
    if client.collections.exists(COLLECTION_NAME):
        client.collections.delete(COLLECTION_NAME)
        print(f"Dropped existing collection '{COLLECTION_NAME}'")

    all_properties = [
        Property(name="title",       data_type=DataType.TEXT),
        Property(name="company",     data_type=DataType.TEXT),
        Property(name="location",    data_type=DataType.TEXT),
        Property(name="description", data_type=DataType.TEXT),
        Property(name="uuid",        data_type=DataType.TEXT),
    ]

    vectorizers = [
        Configure.Vectors.text2vec_mistral(
            name="description_vector",
            source_properties=["description"],
        )
    ]

    client.collections.create(
        name=COLLECTION_NAME,
        properties=all_properties,
        vector_config=vectorizers,
    )

    print(f"Collection '{COLLECTION_NAME}' created.")


def insert_documents(client: weaviate.WeaviateClient, df: pd.DataFrame) -> None:
    """
    Insert rows from a DataFrame into the Weaviate collection.

    Casts all values to str to prevent type errors, skips empty rows,
    and uses batch.dynamic() for efficient insertion.
    """
    collection = client.collections.get(COLLECTION_NAME)
    config = collection.config.get()
    collection_properties = {prop.name for prop in config.properties}

    df = df.astype(str)
    df = df.replace(["", "nan", "None", "NaN", "<NA>"], pd.NA).dropna(how="all")

    inserted = 0
    with collection.batch.dynamic() as batch:
        for index, row in df.iterrows():
            data_object = {
                prop: row[prop]
                for prop in collection_properties
                if prop in row and pd.notna(row[prop])
            }

            if not data_object:
                print(f"Skipping empty row {index}")
                continue

            try:
                batch.add_object(properties=data_object)
                inserted += 1
            except Exception as e:
                print(f"Error adding row {index}: {e}")
                continue

    print(f"Inserted {inserted} documents into '{COLLECTION_NAME}'.")


def _connect() -> weaviate.WeaviateClient:
    url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    api_key = os.getenv("WEAVIATE_API_KEY")
    mistral_api_key = os.getenv("MISTRAL_API_KEY")

    if not mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY env var is not set")

    headers = {"X-Mistral-Api-Key": mistral_api_key}

    if api_key:
        return weaviate.connect_to_weaviate_cloud(
            cluster_url=url,
            auth_credentials=weaviate.auth.AuthApiKey(api_key),
            headers=headers,
        )

    host = url.replace("http://", "").replace("https://", "").split(":")[0]
    port = int(url.split(":")[-1]) if ":" in url.replace("://", "") else 8080
    return weaviate.connect_to_local(host=host, port=port, headers=headers)


def index_jobs() -> None:
    csv_path = os.path.join(os.path.dirname(__file__), "recent_jobs.csv")
    recent_jobs = pd.read_csv(csv_path)
    recent_jobs["uuid"] = [str(uuid.uuid4()) for _ in range(len(recent_jobs))]

    with _connect() as client:
        create_collection(client)
        insert_documents(client, recent_jobs)


if __name__ == "__main__":
    index_jobs()

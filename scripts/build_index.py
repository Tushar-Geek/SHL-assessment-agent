from __future__ import annotations

import asyncio
import pickle

from app.catalog import CatalogRepository
from app.config import get_settings
from app.embeddings import get_embedding_provider
from app.vector_store import VectorStore


async def main() -> None:
    settings = get_settings()
    catalog = CatalogRepository(settings.catalog_path)
    store = VectorStore(get_embedding_provider(settings), catalog.load())
    await store.build()
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    with (settings.index_dir / "metadata.pkl").open("wb") as fh:
        pickle.dump([item.model_dump(mode="json") for item in catalog.load()], fh)
    print(f"Built semantic index metadata at {settings.index_dir}")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Seed ChromaDB with curated CI failure knowledge."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.ingestion import seed_knowledge_base  # noqa: E402


def main() -> None:
    force = "--force" in sys.argv
    n = seed_knowledge_base(force=force)
    if n == 0:
        print("Knowledge base already seeded (pass --force to re-seed).")
    else:
        print(f"Seeded {n} failure knowledge documents into ChromaDB.")


if __name__ == "__main__":
    main()

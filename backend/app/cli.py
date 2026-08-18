"""Local CLI helpers. Folder indexing talks to the running API so the
in-process BM25/vector stores used by Uvicorn actually receive the chunks.

Usage (backend running on :8000):

    python -m app.cli index-folder ..\\docs
    python -m app.cli index-folder C:\\notes --username analyst --password analystpass
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

from app.indexing.folder import load_folder


async def index_folder(
    folder: Path,
    *,
    api: str,
    username: str,
    password: str,
    tenant_id: str,
    max_bytes: int,
) -> int:
    files = load_folder(folder, max_bytes=max_bytes)
    if not files:
        print(f"No indexable text files found in {folder}")
        return 1

    async with httpx.AsyncClient(base_url=api.rstrip("/"), timeout=120.0) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        ok = 0
        for item in files:
            payload = {
                "document_id": item.document_id,
                "tenant_id": tenant_id,
                "text": item.text,
                "metadata": {"source": item.relative, "folder": str(folder)},
            }
            response = await client.post("/api/v1/index", json=payload, headers=headers)
            if response.status_code >= 400:
                print(f"FAIL {item.relative} ({response.status_code}) {response.text[:200]}")
                continue
            body = response.json()
            print(
                f"OK   {item.relative}  chunks={body.get('chunks_created')}  id={item.document_id}"
            )
            ok += 1
        print(f"Indexed {ok}/{len(files)} files from {folder}")
        return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hybrid RAG CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    folder_cmd = sub.add_parser("index-folder", help="Index every text file in a directory")
    folder_cmd.add_argument("folder", help="Folder name or path, e.g. docs or C:\\notes")
    folder_cmd.add_argument("--api", default="http://localhost:8000")
    folder_cmd.add_argument("--username", default="analyst")
    folder_cmd.add_argument("--password", default="analystpass")
    folder_cmd.add_argument("--tenant", default="tenant-a")
    folder_cmd.add_argument("--max-bytes", type=int, default=200_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "index-folder":
        folder = Path(args.folder)
        if not folder.exists():
            print(f"Folder not found: {folder.resolve()}", file=sys.stderr)
            return 1
        return asyncio.run(
            index_folder(
                folder,
                api=args.api,
                username=args.username,
                password=args.password,
                tenant_id=args.tenant,
                max_bytes=args.max_bytes,
            )
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

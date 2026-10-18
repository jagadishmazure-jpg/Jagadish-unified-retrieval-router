"""Load the unstructured corpus: SOP/policy docs + synthetic email threads.

Docs live in docs/sops/ and docs/emails/ as Markdown; each ## section
becomes one retrievable chunk cited as `file §section`.
"""

from __future__ import annotations

from pathlib import Path


def _title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def _chunks(path: Path):
    text = path.read_text(encoding="utf-8")
    chunks = []
    section = path.stem
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("# "):
            continue  # document title: not answer text (RAG-CHUNK-01)
        if line.startswith("## "):
            body = "\n".join(buf).strip()
            if body and len(body.split()) > 4:  # skip title-only intros
                chunks.append((section, body))
            buf = []
            section = line[3:].strip()
        else:
            buf.append(line)
    body = "\n".join(buf).strip()
    if body and len(body.split()) > 4:
        chunks.append((section, body))
    return chunks


def load_corpus(root: str | Path) -> list[dict]:
    root = Path(root)
    corpus: list[dict] = []
    for sub in ("sops", "emails"):
        d = root / sub
        if not d.exists():
            continue
        for path in sorted(d.glob("*.md")):
            for section, text in _chunks(path):
                corpus.append(
                    {
                        "doc": path.name,
                        "set": sub,
                        "title": _title(path),
                        "section": section,
                        "text": text,
                        "citation": f"{path.name} §{section}",
                    }
                )
    return corpus

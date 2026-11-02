from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from .news import search_articles

TOOL_DEFS = [
    {"name": "list_dir", "description": "List files in the current run workspace.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "read_file", "description": "Read a UTF-8 file in the current run workspace.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "search_content", "description": "Search UTF-8 file contents in a workspace directory.",
     "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}, "dir": {"type": "string"}},
                    "required": ["keyword", "dir"]}},
    {"name": "write_file", "description": "Write a UTF-8 note in the current run workspace.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"},
                     "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "bash", "description": "Run a safe workspace inspection command: pwd, date, ls [path], or rg keyword.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "search_news", "description": "Search recent real RSS news by a query. Try English keywords for English feeds; empty query gives recent articles. Returns source IDs for citation.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"},
                     "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["query"]}},
]


def openai_tools() -> list[dict]:
    return [{"type": "function", "function": item} for item in TOOL_DEFS]


class ToolBox:
    def __init__(self, root: Path, articles: list[dict]):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.articles = articles
        self.seen_article_ids: set[str] = set()

    def _safe_path(self, path: str) -> Path:
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("path escapes workspace")
        return target

    def call(self, name: str, args: dict) -> dict:
        try:
            if name == "list_dir":
                path = self._safe_path(str(args["path"]))
                return {"entries": [{"name": p.name, "type": "dir" if p.is_dir() else "file"}
                                    for p in sorted(path.iterdir())[:100]]}
            if name == "read_file":
                path = self._safe_path(str(args["path"]))
                if path.stat().st_size > 100_000:
                    raise ValueError("file too large")
                return {"path": str(path.relative_to(self.root)), "content": path.read_text(encoding="utf-8")}
            if name == "search_content":
                path = self._safe_path(str(args["dir"]))
                keyword = str(args["keyword"])[:100]
                if not keyword:
                    raise ValueError("keyword is empty")
                matches = []
                for file in path.rglob("*"):
                    if (file.is_file() and not file.is_symlink() and
                            file.resolve().is_relative_to(self.root) and file.stat().st_size <= 100_000):
                        for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                            if keyword.casefold() in line.casefold():
                                matches.append({"file": str(file.relative_to(self.root)), "line": number,
                                                "text": line[:200]})
                                if len(matches) >= 30:
                                    return {"matches": matches, "truncated": True}
                return {"matches": matches, "truncated": False}
            if name == "write_file":
                path = self._safe_path(str(args["path"]))
                content = str(args["content"])
                if len(content.encode("utf-8")) > 32_000 or path.suffix not in (".txt", ".md", ".json"):
                    raise ValueError("only notes up to 32 KB (.txt/.md/.json) are allowed")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return {"written": str(path.relative_to(self.root)), "bytes": len(content.encode("utf-8"))}
            if name == "bash":
                return self._bash(str(args["command"]))
            if name == "search_news":
                result = search_articles(self.articles, str(args["query"]),
                                         min(20, max(1, int(args.get("limit", 12)))))
                self.seen_article_ids.update(a["id"] for a in result["articles"])
                return result
            raise ValueError("unknown tool")
        except (OSError, ValueError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def _bash(self, command: str) -> dict:
        parts = shlex.split(command)
        if parts in (["pwd"], ["date"]):
            argv = parts
        elif parts and parts[0] == "ls" and len(parts) <= 2:
            path = self._safe_path(parts[1] if len(parts) == 2 else ".")
            argv = ["ls", str(path)]
        elif len(parts) == 2 and parts[0] == "rg" and not parts[1].startswith("-"):
            argv = ["rg", "--max-count", "5", "--", parts[1], "."]
        else:
            raise ValueError("command not allowlisted")
        result = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, timeout=3)
        return {"stdout": result.stdout[:4000], "stderr": result.stderr[:300],
                "exit_code": result.returncode}

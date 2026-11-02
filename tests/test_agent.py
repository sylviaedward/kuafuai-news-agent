import json

import pytest

from app import agent
from app.tools import ToolBox


ARTICLE = {"id": "source-123", "title": "New agent research", "url": "https://example.org/a",
           "source": "Example", "published_at": "2026-11-02T00:00:00+00:00",
           "excerpt": "A new agent paper."}


class ScriptedClient:
    """A deterministic test double. Production uses the actual model client."""
    def __init__(self):
        self.turn = 0

    def complete(self, messages, tools):
        self.turn += 1
        if self.turn == 1:
            calls = [("a", "bash", {"command": "pwd"}),
                     ("b", "list_dir", {"path": "."})]
        elif self.turn == 2:
            calls = [("c", "read_file", {"path": "preferences.json"}),
                     ("d", "search_news", {"query": "agent"})]
        elif self.turn == 3:
            calls = [("e", "write_file", {"path": "notes.md", "content": "agent: relevant"}),
                     ("f", "search_content", {"keyword": "agent", "dir": "."})]
        else:
            return {"content": json.dumps({"headline": "今日 AI Agent 观察",
                "items": [{"source_id": "source-123", "summary": "一篇新的 Agent 研究。",
                           "why": "与 Agent 订阅相关"}], "closing": "点击原文核实。"})}
        return {"content": None, "tool_calls": [{"id": id_, "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}}
                for id_, name, args in calls]}


def test_agent_chooses_multiple_tool_rounds(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(agent, "retrieve_all_news", lambda: ([ARTICLE], []))
    user = {"name": "Lin", "topics": ["Agent"], "keywords": ["agent"]}
    briefing, trace = agent.run_agent(user, 7, ScriptedClient())
    assert briefing["items"][0]["url"] == ARTICLE["url"]
    assert [step.get("tool") for step in trace if "tool" in step] == [
        "bash", "list_dir", "read_file", "search_news", "write_file", "search_content"]
    assert (tmp_path / "workspaces/7/notes.md").read_text() == "agent: relevant"


def test_toolbox_blocks_path_escape_and_arbitrary_commands(tmp_path):
    box = ToolBox(tmp_path / "workspace", [ARTICLE])
    assert "error" in box.call("read_file", {"path": "../secret.txt"})
    assert "error" in box.call("bash", {"command": "cat /etc/passwd"})
    assert "error" in box.call("write_file", {"path": "../escape.md", "content": "x"})


def test_final_requires_seen_source(tmp_path):
    box = ToolBox(tmp_path / "workspace", [ARTICLE])
    candidate = json.dumps({"headline": "x", "closing": "x", "items": [
        {"source_id": ARTICLE["id"], "summary": "x", "why": "x"}]})
    with pytest.raises(ValueError, match="uncited"):
        agent._validate_briefing(candidate, box)
    box.call("search_news", {"query": "agent"})
    assert agent._validate_briefing(candidate, box)["items"][0]["url"] == ARTICLE["url"]


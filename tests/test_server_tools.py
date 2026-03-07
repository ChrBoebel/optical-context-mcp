from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


def load_server_module():
    server_path = Path(__file__).resolve().parents[1] / "server.py"
    spec = importlib.util.spec_from_file_location("optical_context_server", server_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_server_exposes_expected_tools():
    module = load_server_module()
    tools = asyncio.run(module.mcp.list_tools())
    tool_names = {tool.name for tool in tools}
    assert tool_names == {
        "compress_pdf",
        "get_job_manifest",
        "get_packed_images",
    }

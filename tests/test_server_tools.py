from __future__ import annotations

import asyncio
import pytest

from optical_mcp import server

def test_server_exposes_expected_tools():
    tools = asyncio.run(server.mcp.list_tools())
    tool_names = {tool.name for tool in tools}
    assert tool_names == {
        "compress_pdf",
        "get_job_manifest",
        "get_packed_images",
    }


def test_cli_help_exits_cleanly(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc_info:
        server.main(["--help"])

    assert exc_info.value.code == 0
    assert "optical-context-mcp" in capsys.readouterr().out

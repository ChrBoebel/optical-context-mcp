"""Check that release metadata and the bundled model agree with the built wheel."""

import email
import json
from pathlib import Path
import tomllib
import zipfile

root = Path(__file__).resolve().parents[1]
project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
server = json.loads((root / "server.json").read_text())
version = project["version"]
assert server["version"] == version, "MCP server version differs from Python package"
assert server["packages"][0]["version"] == version, "MCP package version differs"
assert server["packages"][0]["identifier"] == project["name"]

wheels = list((root / "dist").glob("*.whl"))
assert len(wheels) == 1, "Build in a clean dist directory"
with zipfile.ZipFile(wheels[0]) as wheel:
    model = "optical_mcp/model_data/adaptive_image_sizer.pt"
    assert wheel.getinfo(model).file_size > 0, "Bundled sizing model is missing"
    metadata_path = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
    metadata = email.message_from_bytes(wheel.read(metadata_path))
    assert metadata["Version"] == version
    assert "ml" in metadata.get_all("Provides-Extra", [])
    assert f"mcp-name: {server['name']}" in metadata.get_payload()

print(f"Release {version}: wheel, MCP metadata, ml extra and bundled model agree.")

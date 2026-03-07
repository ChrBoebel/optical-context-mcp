# Optical Context MCP

FastMCP server that reads a local PDF, runs the existing optical-compression OCR + dense packing flow, and returns compact packed images to an MCP client.

## Scope

This first version focuses on:

- local PDF path in
- packed PNG images out
- persisted job artifacts for follow-up retrieval

It intentionally does not run the Gemini post-processing step yet.

## Layout

```text
mcp_optical_context/
├── server.py
├── pyproject.toml
├── README.md
├── jobs/                  # generated at runtime, ignored by git
└── optical_mcp/
    ├── __init__.py
    ├── models.py
    ├── service.py
    └── storage.py
```

## Python

The MCP is set up for Python 3.14. The local environment now has Homebrew Python `3.14.3`.

## Setup

From the repository root:

```bash
uv venv --python /opt/homebrew/bin/python3.14 .venv
uv pip install --python .venv/bin/python -e .
```

## Run

Default MCP transport is stdio:

```bash
.venv/bin/python server.py
```

## Tools

- `compress_pdf`: run Mistral OCR plus dense recomposition and create a stored job
- `get_job_manifest`: return the saved manifest for a job
- `get_packed_images`: return one or more saved packed images for a job

## Job Artifacts

Each run creates a directory under `mcp_optical_context/jobs/<job_id>/` with:

- `manifest.json`
- `ocr_markdown.md`
- `packed_001.png`, `packed_002.png`, ...

## Notes

- `MISTRAL_API_KEY` must be available in the environment or repository `.env`.
- Relative PDF paths are resolved against the MCP repository root.
- For large documents, `compress_pdf` returns a manifest plus a limited inline image preview; the rest can be fetched with `get_packed_images`.
- The server is started directly with the venv Python to avoid mixed global/venv CLI resolution.

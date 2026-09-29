# Changelog

## 0.1.5 — 2026-09-29

- Bundle the adaptive figure-sizing checkpoint. Install the optional `ml` extra
  to use it; installations without the ML runtime keep fixed medium sizing.
- Load the checkpoint with `weights_only=True`.
- Raise the FastMCP minimum to 3.2.0 and support the newer Mistral SDK import path.
- Check the built wheel and run its tests before PyPI publication. Publish the
  matching MCP Registry entry after PyPI succeeds, using GitHub OIDC.
- Add a voluntary feedback form for document workflows and installation reports.

## 0.1.4 — 2026-03-08

- Return up to 30 packed images inline by default.

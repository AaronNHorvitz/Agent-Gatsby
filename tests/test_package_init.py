from __future__ import annotations

import agent_gatsby


def test_package_init_exposes_version_and_docstring() -> None:
    assert agent_gatsby.__version__ == "0.1.0"
    assert "Great Gatsby" in (agent_gatsby.__doc__ or "")

from __future__ import annotations

import pytest

from scripts.check_domain_analysis_cutover_manifest import (
    _validate_removed_locator,
)


def test_file_scope_requires_the_whole_legacy_test_file_to_be_removed(
    tmp_path,
) -> None:
    legacy = tmp_path / "tests" / "test_legacy.py"
    legacy.parent.mkdir()
    legacy.write_text("def test_renamed(): pass\n", encoding="utf-8")

    with pytest.raises(ValueError, match="legacy test file still exists"):
        _validate_removed_locator(
            tmp_path,
            {
                "path": "tests/test_legacy.py",
                "scope": "file",
                "anchors": ["test_old_name"],
            },
            "tests.legacy",
            test_locator=True,
        )

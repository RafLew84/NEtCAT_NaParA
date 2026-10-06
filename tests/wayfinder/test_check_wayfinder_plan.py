import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.check_wayfinder_plan import PlanError, validate_plan


FIXTURES = Path(__file__).parent / "fixtures"
FIRST = "issues/01-source.md"
SECOND = "issues/02-output.md"
ENTRY = "- [Choose the output](issues/02-output.md): preserve the source values."


class WayfinderPlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wayfinder-test-")
        self.addCleanup(temporary.cleanup)
        self.plan = Path(temporary.name) / "plan"
        shutil.copytree(FIXTURES / "closed", self.plan)

    def edit(self, name, before, after):
        path = self.plan / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(before, text)
        path.write_text(text.replace(before, after), encoding="utf-8")

    def append(self, name, text):
        with (self.plan / name).open("a", encoding="utf-8") as stream:
            stream.write("\n" + text + "\n")

    def assert_invalid(self, filename, message):
        with self.assertRaises(PlanError) as caught:
            validate_plan(self.plan)
        self.assertIn(filename, str(caught.exception))
        self.assertIn(message, str(caught.exception))

    def test_saved_valid_examples(self):
        self.assertEqual(validate_plan(FIXTURES / "closed"), 2)
        self.assertEqual(validate_plan(FIXTURES / "in_progress"), 2)

    def test_saved_cycle_example(self):
        with self.assertRaisesRegex(PlanError, "dependency cycle: 01 -> 02 -> 01"):
            validate_plan(FIXTURES / "cycle")

    def test_duplicate_ticket_numbers(self):
        shutil.copyfile(self.plan / FIRST, self.plan / "issues/01-another.md")
        self.assert_invalid("01-source.md", "duplicate ticket number 01")

    def test_invalid_ticket_filenames(self):
        source = self.plan / FIRST
        for filename in ("source.md", "1-source.md", "00-source.md", "001-source.md", "01-.md"):
            with self.subTest(filename=filename):
                target = source.with_name(filename)
                source.rename(target)
                try:
                    self.assert_invalid(filename, "ticket")
                finally:
                    target.rename(source)

    def test_invalid_or_duplicate_status_fields(self):
        for filename in ("map.md", FIRST):
            path = self.plan / filename
            original = path.read_text(encoding="utf-8")
            for declaration in ("Status: done", "Status:", "", "Status: resolved\nStatus: open"):
                with self.subTest(filename=filename, declaration=declaration):
                    path.write_text(original.replace("Status: resolved", declaration), encoding="utf-8")
                    self.assert_invalid(Path(filename).name, "Status")
            path.write_text(original, encoding="utf-8")

    def test_missing_dependency_and_bad_dependency_numbers(self):
        path = self.plan / SECOND
        original = path.read_text(encoding="utf-8")
        for dependency, error in (("99", "unknown Blocked by"), ("1", "invalid ticket number"), ("01, 01", "duplicate Blocked by"), ("01,", "invalid ticket number")):
            with self.subTest(dependency=dependency):
                path.write_text(original.replace("Blocked by: 01", "Blocked by: " + dependency), encoding="utf-8")
                self.assert_invalid("02-output.md", error)

    def test_missing_dependency_field(self):
        self.edit(FIRST, "Blocked by: none", "")
        self.assert_invalid("01-source.md", "Blocked by")

    def test_self_dependency(self):
        self.edit(FIRST, "Blocked by: none", "Blocked by: 01")
        self.assert_invalid("01-source.md", "dependency cycle: 01 -> 01")

    def test_resolved_ticket_cannot_depend_on_open_ticket(self):
        self.edit(FIRST, "Status: resolved", "Status: open")
        self.assert_invalid("02-output.md", "depends on unresolved ticket 01")

    def test_answer_missing_duplicate_or_empty(self):
        path = self.plan / SECOND
        original = path.read_text(encoding="utf-8")
        answer = "## Answer\n\nPreserve the selected source values."
        for replacement in ("", "## Answer\n\n", "## Answer\n<!-- not an answer -->\n### Details\n", answer + "\n## Answer\nOther answer."):
            with self.subTest(replacement=replacement):
                path.write_text(original.replace(answer, replacement), encoding="utf-8")
                self.assert_invalid("02-output.md", "Answer")

    def test_comments_do_not_fill_an_empty_answer(self):
        self.edit(SECOND, "Preserve the selected source values.", "## Comments\nHistorical discussion.")
        self.assert_invalid("02-output.md", "empty ## Answer")

    def test_subsection_is_part_of_answer(self):
        self.edit(SECOND, "Preserve the selected source values.", "### Choice\nPreserve the values.")
        self.assertEqual(validate_plan(self.plan), 2)

    def test_examples_and_historical_status_do_not_change_metadata(self):
        self.append(SECOND, "## Comments\nStatus: open\n```markdown\n## Answer\n[x](missing.md)\n```\n`[x](missing.md)`\n<!-- ## Answer\n[x](missing.md) -->")
        self.assertEqual(validate_plan(self.plan), 2)

    def test_resolved_ticket_missing_from_index(self):
        self.edit("map.md", ENTRY, "")
        self.assert_invalid("map.md", "resolved ticket missing from map index: 02-output.md")

    def test_duplicate_map_index_entry(self):
        self.edit("map.md", ENTRY, ENTRY + "\n" + ENTRY)
        self.assert_invalid("map.md", "duplicate Decisions so far entry")

    def test_unresolved_ticket_cannot_be_indexed_as_a_decision(self):
        self.edit(SECOND, "Status: resolved", "Status: claimed")
        self.assert_invalid("map.md", "indexes claimed ticket 02-output.md")

    def test_closed_map_cannot_have_open_or_claimed_ticket(self):
        self.edit("map.md", ENTRY, "")
        path = self.plan / SECOND
        original = path.read_text(encoding="utf-8")
        for status in ("open", "claimed"):
            with self.subTest(status=status):
                path.write_text(original.replace("Status: resolved", "Status: " + status), encoding="utf-8")
                self.assert_invalid("map.md", f"resolved map contains {status} ticket")

    def test_out_of_scope_ticket_is_a_valid_closed_index_entry(self):
        self.edit("map.md", ENTRY, "")
        self.append("map.md", ENTRY)
        self.assertEqual(validate_plan(self.plan), 2)

    def test_missing_or_duplicate_index_section(self):
        self.edit("map.md", "## Decisions so far", "## Other section")
        self.assert_invalid("map.md", "exactly one ## Decisions so far")
        self.edit("map.md", "## Other section", "## Decisions so far")
        self.append("map.md", "## Decisions so far")
        self.assert_invalid("map.md", "exactly one ## Decisions so far")

    def test_missing_local_link_in_ticket(self):
        self.append(FIRST, "[Missing evidence](no-such-evidence.md)")
        self.assert_invalid("01-source.md", "local link target does not exist: no-such-evidence.md")

    def test_checks_links_in_reachable_documents_and_spec(self):
        self.append("evidence.md", "[Missing image](absent.png)")
        self.assert_invalid("evidence.md", "absent.png")
        self.edit("evidence.md", "[Missing image](absent.png)", "")
        (self.plan / "spec.md").write_text("[Missing file](absent.md)", encoding="utf-8")
        self.assert_invalid("spec.md", "absent.md")

    def test_does_not_scan_unlinked_archives(self):
        archive = self.plan / "worktrees" / "archive.md"
        archive.parent.mkdir()
        archive.write_text("[old link](missing.md)", encoding="utf-8")
        self.assertEqual(validate_plan(self.plan), 2)

    def test_local_path_forms(self):
        for name in ("with space.md", "with(nested(parentheses)).md", "zażółć.md", "hash#name.md"):
            (self.plan / name).write_text("Example", encoding="utf-8")
        self.append("map.md", "\n".join([
            '[Spaced](<with space.md> "title")',
            "[Encoded](with%20space.md#part)",
            "[Nested](with(nested(parentheses)).md)",
            "[Unicode](za%C5%BC%C3%B3%C5%82%C4%87.md)",
            "[Hash](hash%23name.md)",
            "![Image-like link](evidence.md)",
            "[Directory](issues/)",
            "[Line](evidence.md:12)",
            "[Line and column](evidence.md:12:3)",
            "[Query](evidence.md?view=full#part)",
            "[Anchor](#destination)",
            f"[Absolute](<{(self.plan / 'evidence.md').as_posix()}>)",
            f"[File URI]({(self.plan / 'evidence.md').as_uri()})",
            "[Remote](https://example.invalid/does-not-exist)",
            "[Remote without scheme](//example.invalid/does-not-exist)",
            "[Email](mailto:example@example.invalid)",
        ]))
        if os.name == "nt":
            self.append("map.md", f"[Windows slash prefix](</{(self.plan / 'evidence.md').as_posix()}>)")
        self.assertEqual(validate_plan(self.plan), 2)

    def test_reference_links_in_index(self):
        self.edit("map.md", ENTRY, "- [Choose the output][output]: preserve values.\n\n[output]: issues/02-output.md")
        self.assertEqual(validate_plan(self.plan), 2)

    def test_nested_link_labels_check_both_image_and_destination(self):
        self.append("map.md", "[Preview ![thumbnail](evidence.md)](absent.md)")
        self.assert_invalid("map.md", "absent.md")
        self.edit("map.md", "](absent.md)", "](evidence.md)")
        self.assertEqual(validate_plan(self.plan), 2)
        self.edit("map.md", "[thumbnail](evidence.md)", "[thumbnail](absent-image.png)")
        self.assert_invalid("map.md", "absent-image.png")

    def test_file_uri_autolinks(self):
        self.append(FIRST, f"<{(self.plan / 'missing.md').as_uri()}>")
        self.assert_invalid("01-source.md", "missing.md")

    def test_file_uri_in_index_is_counted_once(self):
        self.edit("map.md", "(issues/02-output.md)", f"(<{(self.plan / SECOND).as_uri()}>)")
        self.assertEqual(validate_plan(self.plan), 2)

    def test_malformed_link_is_reported_with_source_file(self):
        self.append(FIRST, "[evidence](<unclosed-path.md)")
        self.assert_invalid("01-source.md", "unclosed <...>")

    def test_missing_reference_target_and_undefined_reference(self):
        self.append(FIRST, "[Evidence][missing]")
        self.assert_invalid("01-source.md", "undefined link reference [missing]")
        self.append(FIRST, "[missing]: absent.md")
        self.assert_invalid("01-source.md", "absent.md")

    def test_empty_or_missing_plan_and_invalid_utf8(self):
        with self.assertRaisesRegex(PlanError, "map.md"):
            validate_plan(self.plan / "missing")
        (self.plan / FIRST).write_bytes(b"\xff")
        self.assert_invalid("01-source.md", "cannot read UTF-8")

    def test_plan_without_tickets_is_an_error(self):
        (self.plan / FIRST).unlink()
        (self.plan / SECOND).unlink()
        self.assert_invalid("issues", "no Markdown tickets found")

    def test_utf8_bom_is_accepted(self):
        path = self.plan / FIRST
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")
        self.assertEqual(validate_plan(self.plan), 2)

    def test_cli_success_and_short_failure_without_traceback(self):
        def run(plan):
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_wayfinder_plan.py"), str(plan)],
                cwd=self.plan.parent, capture_output=True, text=True, encoding="utf-8", timeout=10,
            )
        success = run(self.plan)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertIn("2 tickets", success.stdout)
        self.append(SECOND, "## Answer\nDuplicate.")
        failure = run(self.plan)
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(failure.stdout, "")
        self.assertEqual(len(failure.stderr.splitlines()), 1)
        self.assertIn("02-output.md", failure.stderr)
        self.assertNotIn("Traceback", failure.stderr)


if __name__ == "__main__":
    unittest.main()

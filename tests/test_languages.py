import subprocess
import tempfile
import unittest
from pathlib import Path

from memvet.freshness import check_record
from memvet.languages import JavaScriptAdapter
from memvet.models import MemoryRecord
from memvet.symbols import capture_symbol_hashes


def run_git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class LanguageAdapterTests(unittest.TestCase):
    def test_javascript_adapter_indexes_function_and_arrow_definition(self) -> None:
        definitions = JavaScriptAdapter().index_source(
            "function validateOrder(order) { return order.total > 0; }\n"
            "const formatOrder = (order) => `${order.id}`;\n",
            "src/orders.js",
        )

        self.assertEqual(
            {definition.name for definition in definitions},
            {"validateOrder", "formatOrder"},
        )
        self.assertTrue(all(definition.body_hash for definition in definitions))

    def test_javascript_body_change_needs_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init", "-q")
            run_git(repo, "config", "user.email", "test@example.com")
            run_git(repo, "config", "user.name", "Test User")
            source = repo / "orders.js"
            source.write_text("export function validateOrder(order) { return order.total > 0; }\n")
            run_git(repo, "add", "orders.js")
            run_git(repo, "commit", "-qm", "initial orders")
            commit = run_git(repo, "rev-parse", "HEAD")
            record = MemoryRecord(
                id="decision-1",
                title="Order validation",
                content="Orders need a positive total.",
                introduced_commit=commit,
                files=["orders.js"],
                symbols=["validateOrder"],
                symbol_hashes=capture_symbol_hashes(
                    repo,
                    ["orders.js"],
                    ["validateOrder"],
                    commit,
                ),
            )
            source.write_text("export function validateOrder(order) { return order.total >= 0; }\n")
            run_git(repo, "add", "orders.js")
            run_git(repo, "commit", "-qm", "change validation")

            result = check_record(repo, record)

            self.assertEqual(result.status, "needs_revalidation")
            self.assertIn("symbol body changed: validateOrder", result.reasons)

    def test_regex_literal_containing_quotes_does_not_swallow_the_file(self) -> None:
        # Taken from a real portfolio file: the quote characters live inside a
        # character class, so a scanner that treats them as string delimiters
        # loses track of the braces and runs the body to the end of the file.
        source = (
            "export function sanitizeAnswer(text) {\n"
            "  return text.replace(/(?:\\/[^\\s)\"'<>,]*)?/gi, (match) => match);\n"
            "}\n"
            "\n"
            "export function unrelatedHelper(input) {\n"
            "  return input.trim();\n"
            "}\n"
        )

        definitions = {
            definition.name: definition
            for definition in JavaScriptAdapter().index_source(source, "lib/answer.ts")
        }

        self.assertEqual(set(definitions), {"sanitizeAnswer", "unrelatedHelper"})
        self.assertEqual(definitions["sanitizeAnswer"].line_end, 3)

    def test_comment_braces_and_apostrophes_do_not_extend_a_body(self) -> None:
        source = (
            "export function withNotes(value) {\n"
            "  // don't let the { in this comment unbalance the scan\n"
            "  /* nor the } in this one */\n"
            "  return value;\n"
            "}\n"
            "\n"
            "export function afterNotes(value) {\n"
            "  return value;\n"
            "}\n"
        )

        definitions = {
            definition.name: definition
            for definition in JavaScriptAdapter().index_source(source, "lib/notes.ts")
        }

        self.assertEqual(set(definitions), {"withNotes", "afterNotes"})
        self.assertEqual(definitions["withNotes"].line_end, 5)

    def test_division_is_not_mistaken_for_a_regex_literal(self) -> None:
        source = (
            "export function ratio(a, b) {\n"
            '  const label = a / b + "/" + b;\n'
            "  return label;\n"
            "}\n"
            "\n"
            "export function after(value) {\n"
            "  return value;\n"
            "}\n"
        )

        definitions = {
            definition.name: definition
            for definition in JavaScriptAdapter().index_source(source, "lib/ratio.ts")
        }

        self.assertEqual(set(definitions), {"ratio", "after"})
        self.assertEqual(definitions["ratio"].line_end, 4)

    def test_exported_const_object_is_indexed_as_a_symbol(self) -> None:
        source = (
            "export const site = {\n"
            '  name: "Sai",\n'
            "  roles: [{ title: \"Software Engineer\" }],\n"
            "};\n"
            "\n"
            "export const other = 3;\n"
        )

        definitions = {
            definition.name: definition
            for definition in JavaScriptAdapter().index_source(source, "content/site.ts")
        }

        self.assertIn("site", definitions)
        self.assertEqual(definitions["site"].line_end, 4)

    def test_edit_after_a_regex_function_leaves_the_symbol_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init", "-q")
            run_git(repo, "config", "user.email", "test@example.com")
            run_git(repo, "config", "user.name", "Test User")
            source = repo / "answer.ts"
            original = (
                "export function sanitizeAnswer(text) {\n"
                "  return text.replace(/(?:\\/[^\\s)\"'<>,]*)?/gi, (match) => match);\n"
                "}\n"
            )
            source.write_text(original)
            run_git(repo, "add", "answer.ts")
            run_git(repo, "commit", "-qm", "initial answer")
            commit = run_git(repo, "rev-parse", "HEAD")
            record = MemoryRecord(
                id="decision-1",
                title="Answers cite allowlisted domains only",
                content="Invented domains are rewritten.",
                introduced_commit=commit,
                files=["answer.ts"],
                symbols=["sanitizeAnswer"],
                symbol_hashes=capture_symbol_hashes(
                    repo,
                    ["answer.ts"],
                    ["sanitizeAnswer"],
                    commit,
                ),
            )
            source.write_text(
                original
                + "\nexport function unrelatedHelper(input) {\n  return input.trim();\n}\n"
            )
            run_git(repo, "add", "answer.ts")
            run_git(repo, "commit", "-qm", "append an unrelated helper")

            result = check_record(repo, record)

            self.assertEqual(result.status, "active")
            self.assertIn(
                "tracked symbols are unchanged despite file changes",
                result.reasons,
            )

    def test_hashes_from_an_older_adapter_are_recomputed_not_reported_as_drift(
        self,
    ) -> None:
        # Improving the parser changes every body hash. Without a version on the
        # stored hash, an upgrade tells the user that code they never touched
        # has changed, which is the one thing this tool must never do.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init", "-q")
            run_git(repo, "config", "user.email", "test@example.com")
            run_git(repo, "config", "user.name", "Test User")
            source = repo / "orders.ts"
            original = (
                "export function validateOrder(order) {\n"
                "  return order.total > 0;\n"
                "}\n"
            )
            source.write_text(original)
            run_git(repo, "add", "orders.ts")
            run_git(repo, "commit", "-qm", "initial orders")
            commit = run_git(repo, "rev-parse", "HEAD")
            record = MemoryRecord(
                id="decision-1",
                title="Orders need a positive total",
                content="Totals must be positive.",
                introduced_commit=commit,
                files=["orders.ts"],
                symbols=["validateOrder"],
                # A hash produced by an older adapter version.
                symbol_hashes={"validateOrder": "0" * 64},
                hash_version=1,
            )
            source.write_text(
                original + "\nexport function helper(value) {\n  return value;\n}\n"
            )
            run_git(repo, "add", "orders.ts")
            run_git(repo, "commit", "-qm", "append a helper")

            result = check_record(repo, record)

            self.assertEqual(result.status, "active")
            self.assertIn(
                "symbol hashes were recomputed for an updated language adapter",
                result.reasons,
            )


if __name__ == "__main__":
    unittest.main()

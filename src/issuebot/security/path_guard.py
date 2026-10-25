"""Path guard: prevents path traversal, workspace escaping, and test modification."""

import ast
import os
from pathlib import Path

BLOCKED_WRITE_DIRS = {".git", "hidden_tests"}


class PathGuardError(PermissionError):
    """Raised when a file operation violates path security policies."""


class PathGuard:
    """Enforces file system boundaries within the workspace."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def resolve_safe(self, rel_path: str, *, for_write: bool = False) -> Path:
        """Resolve and validate that `rel_path` stays strictly within the workspace.

        Raises PathGuardError if the path is invalid, absolute, escapes via traversal,
        or targets blocked write directories.
        """
        if not rel_path or not rel_path.strip():
            raise PathGuardError("Path must be a non-empty relative path")

        clean = rel_path.strip()
        if os.path.isabs(clean) or clean.startswith(("/", "\\")):
            raise PathGuardError(f"Absolute paths are forbidden: '{rel_path}'")

        # Resolve path against workspace root
        target = (self.workspace_root / clean).resolve()

        if not target.is_relative_to(self.workspace_root):
            raise PathGuardError(f"Path escapes workspace boundaries: '{rel_path}'")

        # Check for escaping symlinks in existing path elements
        current = self.workspace_root
        for part in Path(clean).parts:
            current = current / part
            if current.is_symlink():
                resolved_link = current.resolve()
                if not resolved_link.is_relative_to(self.workspace_root):
                    raise PathGuardError(f"Symlink escapes workspace: '{rel_path}'")

        if for_write:
            rel_parts = target.relative_to(self.workspace_root).parts
            for part in rel_parts:
                if part in BLOCKED_WRITE_DIRS:
                    raise PathGuardError(
                        f"Modifying files in '{part}/' is prohibited for security"
                    )

        return target

    @staticmethod
    def is_test_file(path: Path) -> bool:
        """Check if a path corresponds to a test file."""
        name = path.name.lower()
        parts = [p.lower() for p in path.parts]
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or "tests" in parts
            or "test" in parts
        )

    def validate_test_integrity(
        self, target_path: Path, old_content: str, new_content: str
    ) -> None:
        """Ensure modifications do not delete or weaken existing test assertions.

        Per Section 7.4 and 9.4: modifications that delete or weaken existing tests
        are blocked. Additions are allowed.
        """
        if not self.is_test_file(target_path):
            return

        # New file creation is always allowed
        if not old_content.strip():
            return

        try:
            old_tree = ast.parse(old_content)
            new_tree = ast.parse(new_content)
        except SyntaxError:
            # If there was a syntax error in python parsing, allow edit to fix it
            return

        # Extract test functions
        old_test_funcs = {
            node.name
            for node in ast.walk(old_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        }
        new_test_funcs = {
            node.name
            for node in ast.walk(new_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        }

        # Verify no existing test functions were deleted
        deleted_funcs = old_test_funcs - new_test_funcs
        if deleted_funcs:
            raise PathGuardError(
                f"Deleting or renaming existing test functions is prohibited: {sorted(deleted_funcs)}"
            )

        # Count assertions
        old_assert_count = sum(1 for node in ast.walk(old_tree) if isinstance(node, ast.Assert))
        new_assert_count = sum(1 for node in ast.walk(new_tree) if isinstance(node, ast.Assert))

        if new_assert_count < old_assert_count:
            raise PathGuardError(
                f"Deleting or weakening assertions in existing test files is prohibited "
                f"({old_assert_count} assertions reduced to {new_assert_count}). "
                "You may only add new tests."
            )

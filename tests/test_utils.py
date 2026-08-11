from __future__ import annotations

import unittest

from gitlab_tools.common.utils import WINDOWS_RESERVED_NAMES, slugify_windows_name


class WindowsNameTests(unittest.TestCase):
    def test_reserved_device_basename_with_extension_is_rewritten(self) -> None:
        for value in ("CON.txt", "nul.git", "Com1.repo", "LPT9.data", "AUX.md", "PRN.log"):
            with self.subTest(value=value):
                result = slugify_windows_name(value, fallback_prefix="path-1")
                basename = result.split(".", 1)[0].upper()
                self.assertNotIn(basename, WINDOWS_RESERVED_NAMES)
                self.assertNotEqual(value.casefold(), result.casefold())

    def test_truncation_does_not_leave_windows_trailing_dot_or_space(self) -> None:
        for value in (("a" * 119) + ".x", ("a" * 119) + " x"):
            with self.subTest(value=value):
                result = slugify_windows_name(value, fallback_prefix="path-1")
                self.assertFalse(result.endswith((".", " ")))


if __name__ == "__main__":
    unittest.main()

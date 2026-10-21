"""The env file is read the way systemd reads it, because the deploy relies on that.

The server's `env` is systemd's EnvironmentFile for the running site, and the
deploy hands the same file to the management commands through DJANGO_ENV_FILE.
If the two read it differently, migrate runs with settings the site does not have.
"""

import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from .settings import _read_env_file


class EnvFileTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        # Whatever a test loads is thrown away with the rest of the environment.
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, text, name="env"):
        path = self.folder / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_an_unquoted_value_with_spaces_is_one_value(self):
        # The line that stopped a release when the deploy sourced the file in bash.
        _read_env_file(self.write("KDU_TEST_TERMS=digital marketing,social media marketing\n"))
        self.assertEqual(os.environ["KDU_TEST_TERMS"], "digital marketing,social media marketing")

    def test_quotes_around_a_value_are_dropped_and_dollars_are_kept(self):
        _read_env_file(self.write(
            "KDU_TEST_DOUBLE=\"two words\"\n"
            "KDU_TEST_SINGLE='it$self'\n"
            "KDU_TEST_DOLLAR=ab$cd\n"))
        self.assertEqual(os.environ["KDU_TEST_DOUBLE"], "two words")
        self.assertEqual(os.environ["KDU_TEST_SINGLE"], "it$self")
        self.assertEqual(os.environ["KDU_TEST_DOLLAR"], "ab$cd")

    def test_comments_and_blank_lines_are_skipped(self):
        _read_env_file(self.write("# KDU_TEST_HASH=1\n\n; KDU_TEST_SEMI=1\nKDU_TEST_REAL=a=b\n"))
        self.assertNotIn("KDU_TEST_HASH", os.environ)
        self.assertNotIn("KDU_TEST_SEMI", os.environ)
        self.assertEqual(os.environ["KDU_TEST_REAL"], "a=b")

    def test_a_real_environment_variable_wins(self):
        os.environ["KDU_TEST_SET"] = "from the environment"
        _read_env_file(self.write("KDU_TEST_SET=from the file\n"))
        self.assertEqual(os.environ["KDU_TEST_SET"], "from the environment")

    def test_django_env_file_names_the_file_to_read(self):
        os.environ["DJANGO_ENV_FILE"] = str(self.write("KDU_TEST_NAMED=yes please\n"))
        _read_env_file()
        self.assertEqual(os.environ["KDU_TEST_NAMED"], "yes please")

    def test_a_named_file_that_is_missing_stops_the_command(self):
        os.environ["DJANGO_ENV_FILE"] = str(self.folder / "not-there")
        with self.assertRaisesMessage(RuntimeError, "not-there"):
            _read_env_file()

    def test_a_missing_default_file_is_ignored(self):
        _read_env_file(self.folder / ".env")

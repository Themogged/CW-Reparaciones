import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

import manage


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RuntimeConfigurationTests(SimpleTestCase):
    def _settings_import(self, **overrides):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("DJANGO_")
        }
        environment.update(
            {
                "DJANGO_DEBUG": "false",
                "DJANGO_SECRET_KEY": "test-production-secret-" + ("x" * 64),
                "DJANGO_ALLOWED_HOSTS": "example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
                "DJANGO_EMAIL_USE_TLS": "true",
                "DJANGO_EMAIL_USE_SSL": "false",
            }
        )
        environment.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", "import cvww_proyect.settings"],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            check=False,
        )

    def test_valid_production_mail_configuration_starts(self):
        result = self._settings_import(DJANGO_EMAIL_PORT="587")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_tls_and_ssl_cannot_be_enabled_together(self):
        result = self._settings_import(
            DJANGO_EMAIL_USE_TLS="true",
            DJANGO_EMAIL_USE_SSL="true",
        )
        self.assertNotEqual(result.returncode, 0)

    def test_mail_port_must_be_in_tcp_range(self):
        result = self._settings_import(DJANGO_EMAIL_PORT="70000")
        self.assertNotEqual(result.returncode, 0)

    def test_manage_command_rejects_unsupported_python(self):
        with patch.object(manage.sys, "version_info", (3, 11, 9)):
            with self.assertRaisesRegex(SystemExit, "requiere Python 3.12"):
                manage.main()

import json
import socket
import unittest
from unittest import mock

from helpers import SkillsTestCase, music_asset, run_main, sfx_asset

import search_assets
import validate_catalog


def _no_network(*args, **kwargs):
    raise AssertionError("network access attempted")


class OfflineTests(SkillsTestCase):
    def test_search_and_validate_without_network(self):
        self.env.install("sound-effects", [sfx_asset()])
        self.env.install("background-music", [music_asset()])
        with mock.patch.object(socket, "socket", _no_network), \
             mock.patch.object(socket, "create_connection", _no_network), \
             mock.patch.object(socket, "getaddrinfo", _no_network):
            code, out, _ = run_main(validate_catalog.main, ["--all", "--skills-root", str(self.env.skills_root)])
            self.assertEqual(code, 0, out)
            for skill, query in (("sound-effects", "click"), ("background-music", "calm")):
                code, out, _ = run_main(search_assets.main, ["--catalog", str(self.env.catalog_path(skill)),
                                                             "--query", query, "--json"])
                self.assertEqual(code, 0)
                self.assertEqual(len(json.loads(out)["results"]), 1)
            code, _, _ = run_main(validate_catalog.main, ["--all", "--no-audio-check"])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

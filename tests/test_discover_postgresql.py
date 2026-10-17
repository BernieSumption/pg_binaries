import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import URLError


SPEC = importlib.util.spec_from_file_location(
    "discover_postgresql", Path(__file__).resolve().parents[1] / "tools" / "discover_postgresql.py"
)
discover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discover)


INDEX = """<!DOCTYPE HTML><html><body><table>
<tr><th>Name</th><th>Last modified</th><th>Size</th></tr>
<tr><td><a href="v14.24/">v14.24/</a></td><td>13-Aug-2026 12:53</td><td>-</td></tr>
<tr><td><a href="v15.14/">v15.14/</a></td><td>14-Aug-2025 13:07</td><td>-</td></tr>
<tr><td><a href="v15.15/">v15.15/</a></td><td>13-Nov-2025 14:11</td><td>-</td></tr>
<tr><td><a href="v18.0/">v18.0/</a></td><td>25-Sep-2025 04:36</td><td>-</td></tr>
<tr><td><a href="v19beta1/">v19beta1/</a></td><td>15-Oct-2026 12:00</td><td>-</td></tr>
</table></body></html>"""


class DiscoveryTests(unittest.TestCase):
    def test_live_index_layout_uses_preformatted_links(self):
        html = '<html><body><pre><a href="v15.15/">v15.15/</a> 13-Nov-2025 14:11 -\n'
        html += '<a href="v18.0/">v18.0/</a> 25-Sep-2025 04:36 -</pre></body></html>'
        self.assertEqual(discover.parse_index(html, 15), ["15.15", "18.0"])

    def test_index_discovers_stable_directories_without_relying_on_timestamps(self):
        html = INDEX.replace("13-Nov-2025 14:11", "unparseable and mutable")
        self.assertEqual(discover.parse_index(html, 15), ["15.14", "15.15", "18.0"])

    def test_support_status_and_latest_minor_drive_selection(self):
        support_html = '''<table><tr><th>Version</th><th>Current minor</th><th>Supported</th></tr>
<tr><td>18</td><td>18.0</td><td>Yes</td></tr>
<tr><td>15</td><td>15.15</td><td>Yes</td></tr>
<tr><td>14</td><td>14.24</td><td>No</td></tr></table>'''
        self.assertEqual(discover.parse_supported_majors(support_html, 15), [15, 18])
        notes = {
            "15.15": '<main><p>Release date: 2025-11-13</p></main>',
            "18.0": '<main><p>Release date: 2025-09-25</p></main>',
        }
        fetched = []
        def fetch(version):
            fetched.append(version)
            return notes[version]
        self.assertEqual(discover.discover_releases(INDEX, 15, [15, 18], fetch), [
            {"version": "15.15", "release_date": "2025-11-13"},
            {"version": "18.0", "release_date": "2025-09-25"},
        ])
        self.assertEqual(fetched, ["15.15", "18.0"])

    def test_missing_supported_major_fails(self):
        with self.assertRaisesRegex(discover.DiscoveryError, "lacks a release"):
            discover.discover_releases(INDEX, 15, [15, 16, 18])

    def test_release_notes_without_valid_date_fail_cleanly(self):
        for html in ("<p>No date here</p>", "<p>Release date: 2025-02-30</p>"):
            with self.subTest(html=html), self.assertRaises(discover.DiscoveryError):
                discover.parse_release_date(html, "18.0")

    def test_fetch_release_notes_reports_network_errors(self):
        with patch.object(discover, "urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(discover.DiscoveryError, "cannot fetch official release notes for PostgreSQL 18.0"):
                discover.fetch_release_notes("18.0")

    def test_check_detects_missing_extra_and_changed_dates(self):
        actual = [
            {"version": "15.15", "release_date": "2025-11-13"},
            {"version": "18.0", "release_date": "2025-09-25"},
        ]
        snapshot = {"releases": [
            {"version": "15.15", "release_date": "2025-11-12"},
            {"version": "16.11", "release_date": "2025-11-13"},
        ]}
        self.assertEqual(discover.compare_releases(actual, snapshot),
                         (["18.0"], ["16.11"], ["15.15"]))


if __name__ == "__main__":
    unittest.main()

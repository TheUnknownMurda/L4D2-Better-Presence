"""GM Demo Archive: parsing its profile page (synthetic page in the site's layout, no network) and the cache."""

import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401

from l4d2_rpc import data, gm_archive

# Same layout as personal.php?view=times (2026-10-15): a heading per map, a runs table, per-player sub-tables
PAGE = """
<h3><i class="material-icons">ondemand_video</i> Gun Shop</h3>
<table><tr><th>Category</th><th>Players</th><th>Final Time</th><th>SI/min</th><th>Date</th><th>Download</th></tr>
<tr><td>full-team</td><td>A, B, C, D</td><td>12:09.27</td><td>14.70</td><td>May 30, 2026</td><td>download</td></tr>
<tr><td>solo</td><td>A</td><td>4:32.50</td><td>9.10</td><td>June 1, 2026</td><td>download</td></tr>
<tr><th>Player</th><th>SI%</th><th>Tank%</th><th>CI%</th><th>Kits</th><th>Acc</th><th>SI HS%</th><th>Time Alive</th></tr>
<tr><td>A</td><td>19.00%</td><td>25.00%</td><td>25.00%</td><td>-</td><td>36.19%</td><td>12.23%</td><td>99:59.00</td></tr>
</table>
<h4><i class="material-icons">cable</i></h4>
<h3>The Bridge (cc)</h3>
<table><tr><td>duo</td><td>A, B</td><td>364:09.27</td><td>14.70</td><td>January 6, 2025</td><td>download</td></tr></table>
<h3>Simplex Survival</h3>
<table><tr><td>solo</td><td>A</td><td>50:00.00</td><td>1.0</td><td>January 6, 2025</td><td>download</td></tr></table>
"""


class Parse(unittest.TestCase):
    def test_best_final_time_per_map(self):
        bests = gm_archive.parse_times(PAGE)
        self.assertEqual(bests, {"c1m2_streets": 12 * 60 + 9.27, "c9m1_alleys": 364 * 60 + 9.27})  # custom map ignored

    def test_empty_profile(self):
        self.assertEqual(gm_archive.parse_times('<div class="alert">No recorded runs found.</div>'), {})

    def test_every_survival_map_has_a_site_name(self):
        codes = {m for m, e in data.game_data()["maps"].items() if "survival" in (e.get("mode_names") or {})}
        self.assertEqual(set(gm_archive.SITE_MAPS.values()), codes)

    def test_steam_id64(self):
        self.assertEqual(gm_archive.steam_id64_from_account(1), 76561197960265729)
        self.assertIsNone(gm_archive.steam_id64_from_account(None))


class Cache(unittest.TestCase):
    def test_cache_is_used_only_for_the_same_player(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "gm_records.json"
            path.write_text(json.dumps({"steam_id64": 1, "fetched": 2e9, "bests": {"c1m2_streets": 272}}))
            self.assertEqual(gm_archive.GmArchive(path, 1).bests, {"c1m2_streets": 272.0})
            self.assertEqual(gm_archive.GmArchive(path, 2).bests, {})

    def test_no_steam_id_no_request(self):
        archive = gm_archive.GmArchive(Path(tempfile.gettempdir()) / "nonexistent-gm.json", None)
        archive.refresh_if_due()
        self.assertFalse(archive._busy)


if __name__ == "__main__":
    unittest.main()

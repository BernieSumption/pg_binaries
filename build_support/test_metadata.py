import copy
import json
from pathlib import Path
import tempfile
import unittest

from build_support.metadata import MetadataError, load_package, packages


class MetadataTests(unittest.TestCase):
    def test_current_packages_have_valid_metadata(self):
        declarations = packages()
        self.assertTrue(declarations)
        for name, data in declarations.items():
            self.assertTrue(data["sources"], name)
            self.assertTrue(data["extensions"], name)

    def test_invalid_contract_is_rejected(self):
        valid = load_package("pgvector")
        cases = []
        value = copy.deepcopy(valid)
        value["sources"]["pgvector"]["sha256"] = "bad"
        cases.append(value)
        value = copy.deepcopy(valid)
        value["sources"]["pgvector"]["version"] = "unused"
        cases.append(value)
        value = copy.deepcopy(valid)
        value["extensions"]["vector"]["requires"] = []
        cases.append(value)
        for data in cases:
            with self.subTest(data=data), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                folder = root / "packages/pgvector"
                folder.mkdir(parents=True)
                (folder / "build.json").write_text(json.dumps(data))
                with self.assertRaises(MetadataError):
                    load_package("pgvector", root)

    def test_duplicate_source_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "packages/example"
            folder.mkdir(parents=True)
            (folder / "build.json").write_text('{"sources":{"x":{},"x":{}},"extensions":{}}')
            with self.assertRaisesRegex(MetadataError, "duplicate"):
                load_package("example", root)

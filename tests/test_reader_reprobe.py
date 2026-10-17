"""Read-only Skope preflight must diagnose optional runtime dependency in its own process."""
import unittest
from unittest.mock import patch
from pathlib import Path
from skope import extraction


class ReaderReprobeTests(unittest.TestCase):
    def test_negative_reader_cache_is_refreshed_without_dump_reads(self):
        common = extraction._module()
        with patch.object(common.fastio, '_INDEXED_BZIP2', None), \
             patch.object(extraction.importlib, 'import_module', return_value=object()) as importer:
            details = extraction._refresh_reader(common, Path('example.json.bz2'))
            self.assertTrue(details['reader_importable'])
            self.assertTrue(details['reader_cache_refreshed'])
            self.assertIsNotNone(common.fastio._INDEXED_BZIP2)
            self.assertTrue(details['server_python'])
            importer.assert_called_once_with('indexed_bzip2')

    def test_missing_dependency_is_reported_not_silently_accepted(self):
        common = extraction._module()
        with patch.object(common.fastio, '_INDEXED_BZIP2', None), \
             patch.object(extraction.importlib, 'import_module', side_effect=ImportError('wheel unavailable')):
            details = extraction._refresh_reader(common, Path('example.json.bz2'))
            self.assertFalse(details['reader_importable'])
            self.assertIn('wheel unavailable', details['reader_import_error'])
            self.assertIsNone(common.fastio._INDEXED_BZIP2)

    def test_reader_present_needs_no_new_import(self):
        common = extraction._module()
        with patch.object(common.fastio, '_INDEXED_BZIP2', object()), \
             patch.object(extraction.importlib, 'import_module') as importer:
            details = extraction._refresh_reader(common, Path('example.json.bz2'))
            self.assertTrue(details['reader_importable'])
            self.assertFalse(details['reader_cache_refreshed'])
            importer.assert_not_called()

    def test_non_bzip2_source_does_not_trigger_import(self):
        common = extraction._module()
        with patch.object(common.fastio, '_INDEXED_BZIP2', None), \
             patch.object(extraction.importlib, 'import_module') as importer:
            details = extraction._refresh_reader(common, Path('example.json.gz'))
            self.assertIsNone(details['reader_importable'])
            importer.assert_not_called()


if __name__ == '__main__': unittest.main()

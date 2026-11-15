"""Small format fixtures and malformed-input checks for the Arena snapshot reader."""
import struct
import unittest
from unittest.mock import patch
import json

from scripts.adapters import arena
from scripts.adapters.arena_parquet import Reader, hybrid, read, snappy


def uint(value):
    output = bytearray()
    while value >= 128:
        output.append((value & 127) | 128)
        value >>= 7
    return bytes(output) + bytes([value])


def compact(fields):
    """Encode only the fixture's small Thrift subset, with explicit field IDs."""
    result = bytearray()
    for field, kind, value in fields:
        result.extend(bytes([kind]) + uint(field * 2))
        if kind in (5, 6):
            result.extend(uint(value * 2))
        elif kind == 8:
            result.extend(uint(len(value)) + value)
        elif kind == 12:
            result.extend(value)
        elif kind == 9:
            element, items = value
            result.extend(bytes([(len(items) << 4) | element]))
            for item in items:
                result.extend(uint(len(item)) + item if element == 8 else item)
        else:
            raise AssertionError(kind)
    return bytes(result) + b'\0'


def fixture(dictionary=False, checksum=None, encoding=None):
    # Three rows: ['alpha', None, 'beta'] or [1.25, None, -2.5].
    kind = 6 if dictionary else 5
    schema = [compact([(4, 8, b'schema'), (5, 5, 1)]),
              compact([(1, 5, kind), (3, 5, 1), (4, 8, b'value')])]
    definitions = struct.pack('<I', 2) + b'\x03\x05'
    pages = b''
    if dictionary:
        raw = struct.pack('<I', 5) + b'alpha' + struct.pack('<I', 4) + b'beta'
        pages += compact([(1, 5, 2), (2, 5, len(raw)), (3, 5, len(raw)),
                          (7, 12, compact([(1, 5, 2), (2, 5, 0)]))]) + raw
    data_offset = 4 + len(pages)
    raw = definitions + (b'\x01\x03\x02' if dictionary else struct.pack('<dd', 1.25, -2.5))
    header = [(1, 5, 0), (2, 5, len(raw)), (3, 5, len(raw))]
    if checksum is not None:
        header.append((4, 5, checksum))
    header.append((5, 12, compact([(1, 5, 3), (2, 5, encoding if encoding is not None else 8 if dictionary else 0),
                                   (3, 5, 3), (4, 5, 3)])))
    pages += compact(header) + raw
    info = [(1, 5, kind), (3, 9, (8, [b'value'])), (4, 5, 0), (5, 6, 3), (6, 6, len(pages)),
            (7, 6, len(pages)), (9, 6, data_offset)]
    if dictionary:
        info.append((11, 6, 4))
    chunk = compact([(3, 12, compact(info))])
    group = compact([(1, 9, (12, [chunk])), (3, 6, 3)])
    # Struct-list elements are concatenated self-terminating structs.
    footer = compact([(1, 5, 1), (2, 9, (12, schema)),
                      (3, 6, 3), (4, 9, (12, [group]))])
    return b'PAR1' + pages + footer + struct.pack('<I', len(footer)) + b'PAR1'


class ArenaParquetTests(unittest.TestCase):
    def test_optional_plain_values_and_null(self):
        self.assertEqual(read(fixture()), [{'value': 1.25}, {'value': None}, {'value': -2.5}])

    def test_dictionary_values_and_null(self):
        self.assertEqual(read(fixture(True)), [{'value': 'alpha'}, {'value': None}, {'value': 'beta'}])

    def test_bad_checksum_and_unknown_encoding_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'checksum'):
            read(fixture(checksum=1))
        with self.assertRaisesRegex(ValueError, 'encoding'):
            read(fixture(encoding=9))

    def test_snappy_overlapping_copy_and_bounds(self):
        self.assertEqual(snappy(b'\x05\x00a\x01\x01', 5), b'aaaaa')
        for data, expected in [(b'\x05\x01\x01', 5), (b'\x05\x00a\x01\x01', 4),
                               (b'\x05\x00a', 5), (b'\x01\x04ab', 1)]:
            with self.assertRaises(ValueError):
                snappy(data, expected)

    def test_bit_packed_and_repeated_runs(self):
        self.assertEqual(hybrid(b'\x03\x05', 1, 3), [1, 0, 1])
        self.assertEqual(hybrid(b'\x06\x01', 1, 3), [1, 1, 1])
        for data in [b'', b'\0', b'\x08\x01', b'\x06\x02', b'\x06\x01\0']:
            with self.assertRaises(ValueError):
                hybrid(data, 1, 3)

    def test_truncated_files_and_bad_metadata_fail(self):
        data = fixture()
        for raw in [data[:n] for n in range(len(data))] + [b'PAR1' + b'\xff' * 4 + b'PAR1']:
            with self.assertRaises((ValueError, KeyError, IndexError)):
                read(raw)
        with self.assertRaises(ValueError):
            Reader(b'\xff' * 12).uint()

    def test_snapshot_manifest_pins_shards_and_rejects_missing_parts(self):
        manifest = {'sha': 'a' * 40, 'siblings': [{'rfilename': p} for p in [
            'agent/latest-00000-of-00001.parquet', 'text/latest-00001-of-00002.parquet',
            'text/latest-00000-of-00002.parquet', 'text/full-00000-of-00001.parquet']]}
        revision, files = arena.snapshot_files(manifest)
        self.assertEqual(len(files['text', 'latest']), 2)
        self.assertIn('/resolve/' + revision + '/text/latest-00000-', files['text', 'latest'][0])
        self.assertNotIn(('text', 'full'), files)
        manifest['siblings'].pop(2)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            arena.snapshot_files(manifest)
        manifest['sha'] = '../main'
        with self.assertRaisesRegex(ValueError, 'revision'):
            arena.snapshot_files(manifest)

    def test_collection_preserves_pinned_origin_and_rejects_a_broken_category(self):
        manifest = {'sha': 'a' * 40, 'siblings': [{'rfilename': p} for p in [
            'agent/latest-00000-of-00001.parquet', 'text/latest-00000-of-00001.parquet']]}
        urls = []
        def fetch(url):
            urls.append(url)
            if url == arena.MANIFEST_URL:
                return json.dumps(manifest).encode()
            if url.endswith('/README.md'):
                return b'---\nlicense: cc-by-4.0\n---\n'
            return b'snapshot'
        row = {'model_name': 'Example', 'score': -0.2, 'rating': 1200}
        with patch.object(arena, 'read_parquet', return_value=[row]):
            pack = arena.collect(fetch)
        self.assertEqual(len(pack['observations']), 2)
        for observation in pack['observations']:
            self.assertIn('/resolve/' + 'a' * 40 + '/', observation['source_url'])
        self.assertFalse(any('datasets-server' in url for url in urls))
        with patch.object(arena, 'read_parquet', side_effect=ValueError('broken category')):
            with self.assertRaisesRegex(ValueError, 'broken category'):
                arena.collect(fetch)


if __name__ == '__main__':
    unittest.main()

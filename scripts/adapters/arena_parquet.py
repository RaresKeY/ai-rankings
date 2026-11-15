"""Bounded reader for Arena's flat Parquet snapshots, using only the stdlib.

Supports optional/required primitive columns, PLAIN and RLE_DICTIONARY data
pages (v1), and uncompressed/Snappy/Gzip blocks. Unknown layouts fail closed.
Format references: parquet.apache.org/docs/file-format/ and Google's Snappy
format_description.txt. This is deliberately not a general Parquet engine.
"""
import gzip
import struct
import zlib

LIMIT = 64 * 1024 * 1024
MAX_ROWS = 100_000


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError('Truncated Arena Parquet data')
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result

    def uint(self):
        result = 0
        for shift in range(0, 70, 7):
            byte = self.take(1)[0]
            result |= (byte & 127) << shift
            if byte < 128:
                return result
        raise ValueError('Oversized Parquet integer')

    def integer(self):
        value = self.uint()
        return (value >> 1) ^ -(value & 1)

    def value(self, kind, depth=0):
        if depth > 24:
            raise ValueError('Nested Arena Parquet metadata')
        if kind in (1, 2):
            return kind == 1
        if kind == 3:
            return self.take(1)[0]
        if kind in (4, 5, 6):
            return self.integer()
        if kind == 7:
            return struct.unpack('<d', self.take(8))[0]
        if kind == 8:
            return self.take(self.uint())
        if kind in (9, 10):
            header = self.take(1)[0]
            count = header >> 4
            if count == 15:
                count = self.uint()
            if count > MAX_ROWS:
                raise ValueError('Oversized Parquet metadata list')
            return [self.value(header & 15, depth + 1) for _ in range(count)]
        if kind == 12:
            result, field = {}, 0
            while True:
                header = self.take(1)[0]
                if header == 0:
                    return result
                field = field + (header >> 4) if header >> 4 else self.integer()
                if field in result or len(result) >= 1000:
                    raise ValueError('Invalid Parquet metadata fields')
                result[field] = self.value(header & 15, depth + 1)
        raise ValueError('Unsupported Arena Parquet metadata type')


def snappy(data, expected):
    reader = Reader(data)
    if reader.uint() != expected or not 0 <= expected <= LIMIT:
        raise ValueError('Invalid Snappy output size')
    output = bytearray()
    while reader.pos < len(data):
        tag = reader.take(1)[0]
        kind = tag & 3
        if kind == 0:
            size = tag >> 2
            size = size + 1 if size < 60 else int.from_bytes(reader.take(size - 59), 'little') + 1
            if len(output) + size > expected:
                raise ValueError('Oversized Snappy literal')
            output.extend(reader.take(size))
        else:
            if kind == 1:
                size, offset = 4 + ((tag >> 2) & 7), ((tag & 224) << 3) | reader.take(1)[0]
            else:
                size, offset = 1 + (tag >> 2), int.from_bytes(reader.take(2 if kind == 2 else 4), 'little')
            if not 0 < offset <= len(output) or len(output) + size > expected:
                raise ValueError('Invalid Snappy copy')
            # Overlapping copies repeat the existing suffix, not a padded slice.
            start = len(output) - offset
            pattern = output[start:start + min(size, offset)]
            output.extend((pattern * ((size + len(pattern) - 1) // len(pattern)))[:size])
    if len(output) != expected:
        raise ValueError('Incomplete Snappy output')
    return bytes(output)


def hybrid(data, width, count):
    if not 0 <= width <= 32 or not 0 <= count <= MAX_ROWS:
        raise ValueError('Unsupported Parquet bit width/count')
    reader, values = Reader(data), []
    while len(values) < count:
        header = reader.uint()
        if not header:
            raise ValueError('Empty Parquet RLE run')
        if header & 1:
            size = (header >> 1) * 8
            if size > count - len(values) + 7:
                raise ValueError('Oversized Parquet bit-packed run')
            for _ in range(size // 8):
                packed = int.from_bytes(reader.take(width), 'little')
                values.extend((packed >> (i * width)) & ((1 << width) - 1) for i in range(8))
        else:
            size = header >> 1
            if size > count - len(values):
                raise ValueError('Oversized Parquet RLE run')
            value = int.from_bytes(reader.take((width + 7) // 8), 'little')
            if value >= 1 << width:
                raise ValueError('Invalid Parquet RLE value')
            values.extend([value] * size)
    if reader.pos != len(data):
        raise ValueError('Trailing Parquet RLE bytes')
    return values[:count]


def plain(data, kind, count):
    if not 0 <= count <= MAX_ROWS:
        raise ValueError('Oversized Arena Parquet value count')
    reader = Reader(data)
    if kind == 6:
        values = [reader.take(int.from_bytes(reader.take(4), 'little')).decode('utf-8') for _ in range(count)]
    elif kind in (1, 2, 4, 5):
        code = {1: 'i', 2: 'q', 4: 'f', 5: 'd'}[kind]
        size = struct.calcsize('<' + code)
        values = [struct.unpack('<' + code, reader.take(size))[0] for _ in range(count)]
    elif kind == 0:
        packed = reader.take((count + 7) // 8)
        values = [bool(packed[i // 8] & (1 << (i % 8))) for i in range(count)]
    else:
        raise ValueError('Unsupported Arena Parquet primitive')
    if reader.pos != len(data):
        raise ValueError('Trailing Parquet PLAIN bytes')
    return values


def column(data, meta, optional, count):
    if meta[5] != count or meta[4] not in (0, 1, 2):
        raise ValueError('Unsupported Arena Parquet column')
    start = min(meta[9], meta.get(11, meta[9]))
    reader = Reader(data[start:start + meta[7]])
    dictionary, values, expanded = None, [], 0
    while reader.pos < len(reader.data):
        header = reader.value(12)
        expected = header[2]
        expanded += expected
        if not 0 <= expected <= LIMIT or expanded > meta[6]:
            raise ValueError('Oversized Parquet page')
        compressed = reader.take(header[3])
        if 4 in header and zlib.crc32(compressed) != header[4] & 0xffffffff:
            raise ValueError('Parquet page checksum mismatch')
        if meta[4] == 1:
            block = snappy(compressed, expected)
        elif meta[4] == 2:
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                block = stream.read(expected + 1)
        else:
            block = compressed
        if len(block) != expected:
            raise ValueError('Parquet page size mismatch')
        if header[1] == 2:
            if dictionary is not None or values or header[7][2] != 0:
                raise ValueError('Invalid Parquet dictionary page')
            dictionary = plain(block, meta[1], header[7][1])
        elif header[1] == 0:
            page = header[5]
            size = page[1]
            if not 0 <= size <= count - len(values) or page[3] != 3 or page[4] != 3:
                raise ValueError('Invalid Parquet data page')
            payload = Reader(block)
            defined = hybrid(payload.take(int.from_bytes(payload.take(4), 'little')), 1, size) if optional else [1] * size
            present = sum(defined)
            encoded = payload.take(len(block) - payload.pos)
            if page[2] == 0:
                actual = plain(encoded, meta[1], present)
            elif page[2] in (2, 8) and dictionary is not None:
                indices = hybrid(encoded[1:], encoded[0], present)
                if any(i >= len(dictionary) for i in indices):
                    raise ValueError('Invalid Parquet dictionary index')
                actual = [dictionary[i] for i in indices]
            else:
                raise ValueError('Unsupported Arena Parquet value encoding')
            iterator = iter(actual)
            values.extend(next(iterator) if flag else None for flag in defined)
        else:
            raise ValueError('Unsupported Arena Parquet page version')
    if len(values) != count:
        raise ValueError('Incomplete Arena Parquet column')
    return values


def read(data):
    if not 12 <= len(data) <= LIMIT or data[:4] != b'PAR1' or data[-4:] != b'PAR1':
        raise ValueError('Invalid Arena Parquet file')
    size = int.from_bytes(data[-8:-4], 'little')
    if not 0 < size <= len(data) - 12:
        raise ValueError('Invalid Parquet footer size')
    footer = Reader(data[-8 - size:-8])
    meta = footer.value(12)
    schema = meta[2]
    if footer.pos != size or schema[0].get(5) != len(schema) - 1 or len(schema) > 64:
        raise ValueError('Arena Parquet schema must be flat')
    names = [s[4] for s in schema[1:]]
    if len(set(names)) != len(names) or not 0 <= meta[3] <= MAX_ROWS:
        raise ValueError('Invalid Arena Parquet schema/row count')
    rows, expanded = [], 0
    for group in meta[4]:
        count = group[3]
        if not 0 <= count <= MAX_ROWS - len(rows) or len(group[1]) != len(names):
            raise ValueError('Invalid Parquet row group')
        columns = {}
        for field, chunk in zip(schema[1:], group[1]):
            info = chunk[3]
            expanded += info[6]
            start = min(info[9], info.get(11, info[9]))
            if (1 in chunk or field.get(5) or field.get(3) not in (0, 1)
                    or info[3] != [field[4]] or info[1] != field[1]
                    or start < 4 or info[6] < 0 or expanded > 2 * LIMIT
                    or info[7] < 0 or start + info[7] > len(data) - size - 8):
                raise ValueError('Unsupported Arena Parquet column layout')
            columns[field[4].decode('utf-8')] = column(data, info, field[3] == 1, count)
        rows.extend({name: values[i] for name, values in columns.items()} for i in range(count))
    if len(rows) != meta[3]:
        raise ValueError('Incomplete Arena Parquet rows')
    return rows

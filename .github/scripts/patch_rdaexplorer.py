#!/usr/bin/env python3
"""Make RDAExplorer.dll usable on Linux.

RDAExplorer converts archive paths ("a/b/c.xml") to Windows paths by replacing
"/" with "\\". On Linux "\\" is not a path separator, so Path.GetDirectoryName()
returns "" and Directory.CreateDirectory("") throws.

Fix: change the string literal "\\" in the .NET user-string heap (#US) to "/".
Both literals then have the same length, so the file layout stays identical.
Usage: patch_rdaexplorer.py <RDAExplorer.dll>
"""
import struct
import sys

path = sys.argv[1]
data = bytearray(open(path, "rb").read())

root = data.index(b"BSJB")
ver_len = struct.unpack_from("<I", data, root + 12)[0]
pos = root + 16 + ver_len
n_streams = struct.unpack_from("<H", data, pos + 2)[0]
pos += 4
us_start = us_size = None
for _ in range(n_streams):
    off, size = struct.unpack_from("<II", data, pos)
    end = data.index(b"\0", pos + 8)
    name = data[pos + 8:end].decode()
    pos = (end + 4) & ~3
    if name == "#US":
        us_start, us_size = root + off, size
if us_start is None:
    sys.exit("ERROR: #US heap not found")

# Blob layout: length byte 0x03 (= 1 UTF-16 char + terminator byte), 5C 00, 00
needle = b"\x03\x5c\x00\x00"
heap = bytes(data[us_start:us_start + us_size])
if heap.count(needle) == 0:
    if b"\x03\x2f\x00\x00" in heap and b"\\" not in heap:
        print("Already patched.")
        sys.exit(0)
    sys.exit("ERROR: backslash literal not found")
if heap.count(needle) != 1:
    sys.exit(f"ERROR: expected exactly 1 backslash literal, found {heap.count(needle)}")

idx = us_start + heap.index(needle)
data[idx + 1] = 0x2F  # '\\' -> '/'
open(path, "wb").write(data)
print("Patched RDAExplorer.dll: '\\\\' -> '/'")

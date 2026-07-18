#!/usr/bin/env python3
"""
decode_il.py - CIL disassembler for DMainWidget.onGetPcInfoOk
Maps the 65-byte HID frame construction.

Uses pefile for RVA resolution and manual CIL disassembly with correct opcodes.
Opcode table sourced from ECMA-335 6th Edition and dotnet/runtime OpCodes.cs.
"""

import struct
import sys
from pathlib import Path

EXE_PATH = Path(__file__).parent / "WALRUS_extracted" / "app" / "PcInfoMonitorPro.exe"

# ============================================================
# CIL One-byte opcode table (ECMA-335 III.4.1)
# Format: opcode_byte -> (name, operand_size_bytes, operand_type)
# operand_type: 'none', 'int8', 'uint8', 'int16', 'int32', 'int64',
#               'float32', 'float64', 'token', 'branch8', 'branch32', 'switch'
# ============================================================

OPCODES = {
    # === One-byte opcodes (0x00 - 0xE0) ===
    0x00: ('nop',                'none'),
    0x01: ('break',              'none'),
    0x02: ('ldarg.0',            'none'),
    0x03: ('ldarg.1',            'none'),
    0x04: ('ldarg.2',            'none'),
    0x05: ('ldarg.3',            'none'),
    0x06: ('ldloc.0',            'none'),
    0x07: ('ldloc.1',            'none'),
    0x08: ('ldloc.2',            'none'),
    0x09: ('ldloc.3',            'none'),
    0x0A: ('stloc.0',            'none'),
    0x0B: ('stloc.1',            'none'),
    0x0C: ('stloc.2',            'none'),
    0x0D: ('stloc.3',            'none'),
    0x0E: ('ldarg.s',            'uint8'),      # short inline var
    0x0F: ('ldarga.s',           'uint8'),
    0x10: ('starg.s',            'uint8'),
    0x11: ('ldloc.s',            'uint8'),
    0x12: ('ldloca.s',           'uint8'),
    0x13: ('stloc.s',            'uint8'),
    0x14: ('ldnull',             'none'),
    0x15: ('ldc.i4.m1',          'none'),
    0x16: ('ldc.i4.0',           'none'),
    0x17: ('ldc.i4.1',           'none'),
    0x18: ('ldc.i4.2',           'none'),
    0x19: ('ldc.i4.3',           'none'),
    0x1A: ('ldc.i4.4',           'none'),
    0x1B: ('ldc.i4.5',           'none'),
    0x1C: ('ldc.i4.6',           'none'),
    0x1D: ('ldc.i4.7',           'none'),
    0x1E: ('ldc.i4.8',           'none'),
    0x1F: ('ldc.i4.s',           'int8'),       # short inline int
    0x20: ('ldc.i4',             'int32'),      # inline int
    0x21: ('ldc.i8',             'int64'),      # inline int64
    0x22: ('ldc.r4',             'float32'),    # inline float
    0x23: ('ldc.r8',             'float64'),    # inline float (double)
    # 0x24: unused
    0x25: ('dup',                'none'),
    0x26: ('pop',                'none'),
    0x27: ('jmp',                'token'),      # inline method
    0x28: ('call',               'token'),      # inline method
    0x29: ('calli',              'token'),      # inline sig (standalone sig)
    0x2A: ('ret',                'none'),
    0x2B: ('br.s',               'int8'),       # short branch offset
    0x2C: ('brfalse.s',          'int8'),
    0x2D: ('brtrue.s',           'int8'),
    0x2E: ('beq.s',              'int8'),
    0x2F: ('bge.s',              'int8'),
    0x30: ('bgt.s',              'int8'),
    0x31: ('ble.s',              'int8'),
    0x32: ('blt.s',              'int8'),
    0x33: ('bne.un.s',           'int8'),
    0x34: ('bge.un.s',           'int8'),
    0x35: ('bgt.un.s',           'int8'),
    0x36: ('ble.un.s',           'int8'),
    0x37: ('blt.un.s',           'int8'),
    0x38: ('br',                 'int32'),      # long branch offset
    0x39: ('brfalse',            'int32'),
    0x3A: ('brtrue',             'int32'),
    0x3B: ('beq',                'int32'),
    0x3C: ('bge',                'int32'),
    0x3D: ('bgt',                'int32'),
    0x3E: ('ble',                'int32'),
    0x3F: ('blt',                'int32'),
    0x40: ('bne.un',             'int32'),
    0x41: ('bge.un',             'int32'),
    0x42: ('bgt.un',             'int32'),
    0x43: ('ble.un',             'int32'),
    0x44: ('blt.un',             'int32'),
    0x45: ('switch',             'switch'),     # variable length
    0x46: ('ldind.i1',           'none'),
    0x47: ('ldind.u1',           'none'),
    0x48: ('ldind.i2',           'none'),
    0x49: ('ldind.u2',           'none'),
    0x4A: ('ldind.i4',           'none'),
    0x4B: ('ldind.u4',           'none'),
    0x4C: ('ldind.i8',           'none'),
    0x4D: ('ldind.i',            'none'),
    0x4E: ('ldind.r4',           'none'),
    0x4F: ('ldind.r8',           'none'),
    0x50: ('ldind.ref',          'none'),
    0x51: ('stind.ref',          'none'),
    0x52: ('stind.i1',           'none'),
    0x53: ('stind.i2',           'none'),
    0x54: ('stind.i4',           'none'),
    0x55: ('stind.i8',           'none'),
    0x56: ('stind.r4',           'none'),
    0x57: ('stind.r8',           'none'),
    0x58: ('add',                'none'),
    0x59: ('sub',                'none'),
    0x5A: ('mul',                'none'),
    0x5B: ('div',                'none'),
    0x5C: ('div.un',             'none'),
    0x5D: ('rem',                'none'),
    0x5E: ('rem.un',             'none'),
    0x5F: ('and',                'none'),
    0x60: ('or',                 'none'),
    0x61: ('xor',                'none'),
    0x62: ('shl',                'none'),
    0x63: ('shr',                'none'),
    0x64: ('shr.un',             'none'),
    0x65: ('neg',                'none'),
    0x66: ('not',                'none'),
    0x67: ('conv.i1',            'none'),
    0x68: ('conv.i2',            'none'),
    0x69: ('conv.i4',            'none'),
    0x6A: ('conv.i8',            'none'),
    0x6B: ('conv.r4',            'none'),
    0x6C: ('conv.r8',            'none'),
    0x6D: ('conv.u4',            'none'),
    0x6E: ('conv.u8',            'none'),
    0x6F: ('callvirt',           'token'),      # inline method
    0x70: ('cpobj',              'token'),      # inline type
    0x71: ('ldobj',              'token'),      # inline type
    0x72: ('ldstr',              'token'),      # inline string
    0x73: ('newobj',             'token'),      # inline method
    0x74: ('castclass',          'token'),      # inline type
    0x75: ('isinst',             'token'),      # inline type
    0x76: ('conv.r.un',          'none'),
    # 0x77, 0x78: unused
    0x79: ('unbox',              'token'),      # inline type
    0x7A: ('throw',              'none'),
    0x7B: ('ldfld',              'token'),      # inline field
    0x7C: ('ldflda',             'token'),      # inline field
    0x7D: ('stfld',              'token'),      # inline field
    0x7E: ('ldsfld',             'token'),      # inline field
    0x7F: ('ldsflda',            'token'),      # inline field
    0x80: ('stsfld',             'token'),      # inline field
    0x81: ('stobj',              'token'),      # inline type
    0x82: ('conv.ovf.i1.un',     'none'),
    0x83: ('conv.ovf.i2.un',     'none'),
    0x84: ('conv.ovf.i4.un',     'none'),
    0x85: ('conv.ovf.i8.un',     'none'),
    0x86: ('conv.ovf.u1.un',     'none'),
    0x87: ('conv.ovf.u2.un',     'none'),
    0x88: ('conv.ovf.u4.un',     'none'),
    0x89: ('conv.ovf.u8.un',     'none'),
    0x8A: ('conv.ovf.i.un',      'none'),
    0x8B: ('conv.ovf.u.un',      'none'),
    0x8C: ('box',                'token'),      # inline type
    0x8D: ('newarr',             'token'),      # inline type
    0x8E: ('ldlen',              'none'),
    0x8F: ('ldelema',            'token'),      # inline type
    0x90: ('ldelem.i1',          'none'),
    0x91: ('ldelem.u1',          'none'),
    0x92: ('ldelem.i2',          'none'),
    0x93: ('ldelem.u2',          'none'),
    0x94: ('ldelem.i4',          'none'),
    0x95: ('ldelem.u4',          'none'),
    0x96: ('ldelem.i8',          'none'),
    0x97: ('ldelem.i',           'none'),
    0x98: ('ldelem.r4',          'none'),
    0x99: ('ldelem.r8',          'none'),
    0x9A: ('ldelem.ref',         'none'),
    0x9B: ('stelem.i',           'none'),
    0x9C: ('stelem.i1',          'none'),
    0x9D: ('stelem.i2',          'none'),
    0x9E: ('stelem.i4',          'none'),
    0x9F: ('stelem.i8',          'none'),
    0xA0: ('stelem.r4',          'none'),
    0xA1: ('stelem.r8',          'none'),
    0xA2: ('stelem.ref',         'none'),
    0xA3: ('ldelem',             'token'),      # inline type
    0xA4: ('stelem',             'token'),      # inline type
    0xA5: ('unbox.any',          'token'),      # inline type
    # 0xA6-0xB2: unused
    0xB3: ('conv.ovf.i1',        'none'),
    0xB4: ('conv.ovf.u1',        'none'),
    0xB5: ('conv.ovf.i2',        'none'),
    0xB6: ('conv.ovf.u2',        'none'),
    0xB7: ('conv.ovf.i4',        'none'),
    0xB8: ('conv.ovf.u4',        'none'),
    0xB9: ('conv.ovf.i8',        'none'),
    0xBA: ('conv.ovf.u8',        'none'),
    # 0xBB-0xC1: unused
    0xC2: ('refanyval',          'token'),      # inline type
    0xC3: ('ckfinite',           'none'),
    # 0xC4-0xC5: unused
    0xC6: ('mkrefany',           'token'),      # inline type
    # 0xC7-0xCF: unused
    0xD0: ('ldtoken',            'token'),      # inline type
    0xD1: ('conv.u2',            'none'),
    0xD2: ('conv.u1',            'none'),
    0xD3: ('conv.i',             'none'),
    0xD4: ('conv.ovf.i',         'none'),
    0xD5: ('conv.ovf.u',         'none'),
    0xD6: ('add.ovf',            'none'),
    0xD7: ('add.ovf.un',         'none'),
    0xD8: ('mul.ovf',            'none'),
    0xD9: ('mul.ovf.un',         'none'),
    0xDA: ('sub.ovf',            'none'),
    0xDB: ('sub.ovf.un',         'none'),
    0xDC: ('endfinally',         'none'),
    0xDD: ('leave',              'int32'),      # long branch target
    0xDE: ('leave.s',            'int8'),       # short branch target
    0xDF: ('stind.i',            'none'),
    0xE0: ('conv.u',             'none'),
    # 0xE1-0xF7: unused / reserved
    # 0xF8-0xFB: reserved (prefix3-6)
    # 0xFC: prefix3
    # 0xFD: prefix2 (not used for two-byte; 0xFE is the prefix)
}

# Two-byte opcodes (0xFE prefix)
# Source: ECMA-335 III.4.1, dotnet/runtime OpCodes.cs
TWO_BYTE = {
    0x00: ('arglist',            'none'),
    0x01: ('ceq',                'none'),
    0x02: ('cgt',                'none'),
    0x03: ('cgt.un',             'none'),
    0x04: ('clt',                'none'),
    0x05: ('clt.un',             'none'),
    0x06: ('ldftn',              'token'),      # inline method
    0x07: ('ldvirtftn',          'token'),      # inline method
    # 0x08: unused
    0x09: ('ldarg',              'uint16'),     # inline uint16
    0x0A: ('ldarga',             'uint16'),     # inline uint16
    0x0B: ('starg',              'uint16'),     # inline uint16
    0x0C: ('ldloc',              'uint16'),     # inline uint16
    0x0D: ('ldloca',             'uint16'),     # inline uint16
    0x0E: ('stloc',              'uint16'),     # inline uint16
    0x0F: ('localloc',           'none'),
    # 0x10: unused
    0x11: ('endfilter',          'none'),
    0x12: ('unaligned.',         'uint8'),      # prefix, 1-byte alignment
    0x13: ('volatile.',          'none'),       # prefix
    0x14: ('tail.',              'none'),       # prefix
    0x15: ('initobj',            'token'),      # inline type
    0x16: ('constrained.',       'token'),      # prefix, inline type
    0x17: ('cpblk',              'none'),
    0x18: ('initblk',            'none'),
    # 0x19: unused
    0x1A: ('rethrow',            'none'),
    # 0x1B: unused
    0x1C: ('sizeof',             'token'),      # inline type
    0x1D: ('refanytype',         'none'),
    0x1E: ('readonly.',          'none'),       # prefix
}


# ============================================================
# Minimal PE reader
# ============================================================

def read_u16(data, off):
    return struct.unpack_from('<H', data, off)[0]

def read_u32(data, off):
    return struct.unpack_from('<I', data, off)[0]

def read_i32(data, off):
    return struct.unpack_from('<i', data, off)[0]

def read_i8(b):
    """Signed byte to int"""
    return b if b < 0x80 else b - 0x100


class PEFile:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        pe_off = read_u32(self.data, 0x3C)
        coff = pe_off + 4
        self.num_sections = read_u16(self.data, coff + 2)
        self.size_opt = read_u16(self.data, coff + 16)
        sec_off = coff + 20 + self.size_opt
        self.sections = []
        for i in range(self.num_sections):
            off = sec_off + i * 40
            name = self.data[off:off+8].rstrip(b'\x00').decode('ascii', errors='replace')
            vsize = read_u32(self.data, off + 8)
            va = read_u32(self.data, off + 12)
            raw_ptr = read_u32(self.data, off + 20)
            self.sections.append({'name': name, 'va': va, 'raw_ptr': raw_ptr, 'vsize': vsize})

    def rva_to_offset(self, rva):
        for sec in self.sections:
            if sec['va'] <= rva < sec['va'] + sec['vsize']:
                return rva - sec['va'] + sec['raw_ptr']
        return None

    def read_rva(self, rva, size):
        off = self.rva_to_offset(rva)
        if off is None:
            return None
        return self.data[off:off + size]


# ============================================================
# Token resolver using dnfile
# ============================================================

class TokenResolver:
    def __init__(self, path):
        import dnfile
        self.dn = dnfile.dnPE(str(path))
        self.md = self.dn.net
        self.method_table = list(self.md.mdtables.MethodDef)
        self.typedef_table = list(self.md.mdtables.TypeDef)
        self.typeref_table = list(self.md.mdtables.TypeRef)
        self.memberref_table = list(self.md.mdtables.MemberRef)
        self.field_table = list(self.md.mdtables.Field)
        self.standalonesig_table = list(self.md.mdtables.StandAloneSig) if hasattr(self.md.mdtables, 'StandAloneSig') and self.md.mdtables.StandAloneSig else []

    def get_string(self, item):
        if hasattr(item, 'value'):
            return str(item.value)
        try:
            return self.md.strings.get_str(int(item))
        except Exception:
            return str(item)

    def resolve(self, token):
        if token == 0:
            return "<null>"
        table = (token >> 24) & 0xFF
        row = token & 0xFFFFFF

        if table == 0x06 and 1 <= row <= len(self.method_table):
            m = self.method_table[row - 1]
            name = self.get_string(m.Name)
            # Find owner type
            owner = "<unknown>"
            for i, td in enumerate(self.typedef_table):
                try:
                    first = td.FirstMethod.row_index if hasattr(td.FirstMethod, 'row_index') else int(td.FirstMethod)
                    if i + 1 < len(self.typedef_table):
                        next_td = self.typedef_table[i + 1]
                        next_first = next_td.FirstMethod.row_index if hasattr(next_td.FirstMethod, 'row_index') else int(next_td.FirstMethod)
                    else:
                        next_first = len(self.method_table) + 1
                    if first <= row < next_first:
                        ns = self.get_string(td.TypeNamespace)
                        nm = self.get_string(td.TypeName)
                        owner = f"{ns}.{nm}" if ns else nm
                        break
                except Exception:
                    continue
            return f"{owner}::{name}"

        if table == 0x0A and 1 <= row <= len(self.memberref_table):
            mr = self.memberref_table[row - 1]
            name = self.get_string(mr.Name)
            try:
                cls = mr.Class
                if hasattr(cls, 'row_index'):
                    ref_idx = cls.row_index
                    if 1 <= ref_idx <= len(self.typeref_table):
                        t = self.typeref_table[ref_idx - 1]
                        ns = self.get_string(t.TypeNamespace)
                        nm = self.get_string(t.TypeName)
                        prefix = f"{ns}.{nm}" if ns else nm
                        return f"{prefix}::{name}"
            except Exception:
                pass
            return f"MemberRef::{name}"

        if table == 0x04 and 1 <= row <= len(self.field_table):
            f = self.field_table[row - 1]
            return f"Field:{self.get_string(f.Name)}"

        if table == 0x01 and 1 <= row <= len(self.typeref_table):
            t = self.typeref_table[row - 1]
            ns = self.get_string(t.TypeNamespace)
            nm = self.get_string(t.TypeName)
            return f"{ns}.{nm}" if ns else nm

        if table == 0x11 and 1 <= row <= len(self.standalonesig_table):
            return f"StandAloneSig[{row}]"

        return f"Token({table:02X}_{row})"


# ============================================================
# CIL Disassembler
# ============================================================

def disassemble(code, resolver):
    """
    Disassemble CIL bytecode. Returns list of (offset, mnemonic, operand_display, operand_value).
    """
    result = []
    pos = 0

    while pos < len(code):
        addr = pos
        b = code[pos]; pos += 1

        if b == 0xFE:
            # Two-byte opcode
            if pos >= len(code):
                result.append((addr, "FE_???", "<truncated>", None))
                break
            b2 = code[pos]; pos += 1
            if b2 in TWO_BYTE:
                name, op_type = TWO_BYTE[b2]
                full = name
            else:
                full = f"FE_??(0x{b2:02x})"
                op_type = 'none'
        elif b in OPCODES:
            name, op_type = OPCODES[b]
            full = name
        else:
            full = f"??(0x{b:02x})"
            op_type = 'none'

        # Read operand based on type
        op_val = None
        op_display = ""

        if op_type == 'none':
            pass

        elif op_type == 'switch':
            # switch: uint32 count, then count * int32 offsets
            if pos + 4 <= len(code):
                count = read_u32(code, pos); pos += 4
                targets = []
                for _ in range(count):
                    if pos + 4 <= len(code):
                        off = read_i32(code, pos); pos += 4
                        targets.append(f"IL_{(addr + 5 + off):04x}")
                    else:
                        pos += 4
                op_display = f"({count} cases: {', '.join(targets)})"
            continue  # don't add to result since we printed inline

        elif op_type == 'int8':
            raw = code[pos]; pos += 1
            op_val = read_i8(raw)
            op_display = f"{op_val}"

        elif op_type == 'uint8':
            raw = code[pos]; pos += 1
            op_val = raw
            op_display = f"{raw}"

        elif op_type == 'int32':
            raw = read_i32(code, pos); pos += 4
            op_val = raw
            op_display = f"{raw}"

        elif op_type == 'uint16':
            raw = read_u16(code, pos); pos += 2
            op_val = raw
            op_display = f"{raw}"

        elif op_type == 'int64':
            raw = struct.unpack_from('<q', code, pos)[0]; pos += 8
            op_val = raw
            op_display = f"0x{raw:016x}"

        elif op_type == 'float32':
            raw = struct.unpack_from('<f', code, pos)[0]; pos += 4
            op_val = raw
            op_display = f"{raw}"

        elif op_type == 'float64':
            raw = struct.unpack_from('<d', code, pos)[0]; pos += 8
            op_val = raw
            op_display = f"{raw}"

        elif op_type == 'token':
            raw = read_u32(code, pos); pos += 4
            op_val = raw
            op_display = resolver.resolve(raw)

        result.append((addr, full, op_display, op_val))

    return result


# ============================================================
# Stack tracer for stelem analysis
# ============================================================

def trace_stores(code, resolver):
    """
    Walk the IL and track stack to identify stelem operations with their indices and values.
    Returns list of dicts describing each store.
    """
    pos = 0
    stack = []  # Each entry: (description, addr, concrete_int_or_None)
    stores = []

    while pos < len(code):
        addr = pos
        b = code[pos]; pos += 1

        if b == 0xFE:
            b2 = code[pos]; pos += 1
            if b2 in TWO_BYTE:
                name, op_type = TWO_BYTE[b2]
            else:
                name, op_type = f"FE_???", 'none'
        elif b in OPCODES:
            name, op_type = OPCODES[b]
        else:
            name, op_type = f"??(0x{b:02x})", 'none'

        # Read operand
        op_val = None
        if op_type == 'switch':
            if pos + 4 <= len(code):
                count = read_u32(code, pos); pos += 4
                pos += count * 4
            continue
        elif op_type == 'int8':
            raw = code[pos]; pos += 1
            op_val = read_i8(raw)
        elif op_type == 'uint8':
            op_val = code[pos]; pos += 1
        elif op_type == 'int32':
            op_val = read_i32(code, pos); pos += 4
        elif op_type == 'uint16':
            op_val = read_u16(code, pos); pos += 2
        elif op_type == 'int64':
            op_val = struct.unpack_from('<q', code, pos)[0]; pos += 8
        elif op_type == 'float32':
            pos += 4
        elif op_type == 'float64':
            pos += 8
        elif op_type == 'token':
            op_val = read_u32(code, pos); pos += 4

        # --- Stack tracking ---
        const = None

        # Load constant
        if name == 'ldc.i4.m1':
            stack.append(("const(-1)", addr, -1))
        elif name.startswith('ldc.i4.') and name != 'ldc.i4.s':
            try:
                const = int(name.split('.')[-1])
            except ValueError:
                pass
            stack.append((f"const({const})", addr, const))
        elif name == 'ldc.i4.s':
            stack.append((f"const({op_val})", addr, op_val))
        elif name == 'ldc.i4':
            stack.append((f"const({op_val})", addr, op_val))

        # Load arg
        elif name == 'ldarg.0':
            stack.append(("this", addr, None))
        elif name in ('ldarg.1', 'ldarg.2', 'ldarg.3'):
            stack.append((f"arg{int(name[-1])}", addr, None))
        elif name == 'ldarg.s':
            stack.append((f"arg{op_val}", addr, None))
        elif name == 'ldarg' and op_type == 'uint16':
            stack.append((f"arg{op_val}", addr, None))

        # Load local
        elif name in ('ldloc.0', 'ldloc.1', 'ldloc.2', 'ldloc.3'):
            stack.append((f"loc{int(name[-1])}", addr, None))
        elif name == 'ldloc.s':
            stack.append((f"loc{op_val}", addr, None))
        elif name == 'ldloc' and op_type == 'uint16':
            stack.append((f"loc{op_val}", addr, None))

        # Load local address
        elif name in ('ldloca.0', 'ldloca.1', 'ldloca.2', 'ldloca.3'):
            stack.append((f"&loc{int(name[-1])}", addr, None))
        elif name == 'ldloca.s':
            stack.append((f"&loc{op_val}", addr, None))

        # newarr
        elif name == 'newarr':
            if stack:
                cnt_desc, _, _ = stack.pop()
                stack.append((f"new_arr({cnt_desc})", addr, None))

        # ldlen
        elif name == 'ldlen':
            if stack:
                arr_desc, _, _ = stack.pop()
                stack.append((f"len({arr_desc})", addr, None))

        # ldfld
        elif name == 'ldfld':
            if stack:
                obj, _, _ = stack.pop()
                stack.append((f"{obj}.field", addr, None))

        # ldsfld
        elif name == 'ldsfld':
            stack.append(("static_field", addr, None))

        # ldind.i4: load int from address
        elif name == 'ldind.i4':
            if stack:
                addr_desc, _, _ = stack.pop()
                stack.append((f"*({addr_desc})", addr, None))

        # dup
        elif name == 'dup':
            if stack:
                top = stack[-1]
                stack.append((top[0], addr, top[2]))

        # Conversion
        elif name in ('conv.i1', 'conv.u1', 'conv.ovf.i1', 'conv.ovf.u1'):
            if stack:
                v, o, c = stack.pop()
                stack.append((f"byte({v})", o, c & 0xFF if c is not None else None))
        elif name in ('conv.i2', 'conv.u2', 'conv.ovf.i2', 'conv.ovf.u2'):
            if stack:
                v, o, c = stack.pop()
                stack.append((f"short({v})", o, c & 0xFFFF if c is not None else None))
        elif name in ('conv.i4', 'conv.u4', 'conv.ovf.i4', 'conv.ovf.u4'):
            if stack:
                v, o, c = stack.pop()
                stack.append((f"int({v})", o, c if c is not None else None))
        elif name in ('conv.r4',):
            if stack:
                v, o, c = stack.pop()
                stack.append((f"float({v})", o, None))
        elif name in ('conv.r8', 'conv.r.un'):
            if stack:
                v, o, c = stack.pop()
                stack.append((f"double({v})", o, None))

        # Arithmetic
        elif name in ('add', 'sub', 'mul', 'div', 'and', 'or', 'xor', 'shl', 'shr', 'shr.un', 'rem'):
            if len(stack) >= 2:
                r, _, rc = stack.pop()
                l, _, lc = stack.pop()
                cc = None
                if lc is not None and rc is not None:
                    try:
                        if name == 'add': cc = lc + rc
                        elif name == 'sub': cc = lc - rc
                        elif name == 'mul': cc = lc * rc
                        elif name == 'div': cc = lc // rc if rc else None
                        elif name == 'rem': cc = lc % rc if rc else None
                        elif name == 'and': cc = lc & rc
                        elif name == 'or': cc = lc | rc
                        elif name == 'xor': cc = lc ^ rc
                        elif name == 'shl': cc = (lc << rc) & 0xFFFFFFFF
                        elif name == 'shr': cc = lc >> rc
                        elif name == 'shr.un': cc = (lc % (1 << 32)) >> rc
                    except Exception:
                        pass
                stack.append((f"({l} {name} {r})", addr, cc))

        elif name == 'neg':
            if stack:
                v, o, c = stack.pop()
                stack.append((f"-({v})", o, -c if c is not None else None))

        elif name == 'not':
            if stack:
                v, o, c = stack.pop()
                stack.append((f"~({v})", o, ~c if c is not None else None))

        # stelem: array, index, value
        elif name in ('stelem.i1', 'stelem.i2', 'stelem.i4', 'stelem.i8', 'stelem.r4', 'stelem.r8', 'stelem.ref'):
            val_desc, val_addr, val_const = ("?", addr, None)
            idx_desc, idx_addr, idx_const = ("?", addr, None)
            arr_desc, arr_addr, arr_const = ("?", addr, None)
            if len(stack) >= 3:
                val_desc, val_addr, val_const = stack.pop()
                idx_desc, idx_addr, idx_const = stack.pop()
                arr_desc, arr_addr, arr_const = stack.pop()
            stores.append({
                'addr': addr,
                'elem_type': name.split('.')[-1],
                'array': arr_desc,
                'array_addr': arr_addr,
                'index': idx_desc,
                'index_addr': idx_addr,
                'index_const': idx_const,
                'value': val_desc,
                'value_addr': val_addr,
                'value_const': val_const,
            })
            stack.append(("<stelem>", addr, None))

        # stfld: obj, value
        elif name == 'stfld':
            if len(stack) >= 2:
                val_desc, val_addr, val_const = stack.pop()
                obj_desc, obj_addr, _ = stack.pop()
                stores.append({
                    'addr': addr,
                    'elem_type': 'field',
                    'array': obj_desc,
                    'array_addr': obj_addr,
                    'index': f".{resolver.resolve(op_val)}" if op_val else "?",
                    'index_addr': addr,
                    'index_const': None,
                    'value': val_desc,
                    'value_addr': val_addr,
                    'value_const': val_const,
                })

        # stsfld: value
        elif name == 'stsfld':
            if stack:
                val_desc, val_addr, val_const = stack.pop()
                stores.append({
                    'addr': addr,
                    'elem_type': 'static_field',
                    'array': 'static',
                    'array_addr': addr,
                    'index': resolver.resolve(op_val) if op_val else "?",
                    'index_addr': addr,
                    'index_const': None,
                    'value': val_desc,
                    'value_addr': val_addr,
                    'value_const': val_const,
                })

        # ldelema/ldelem: array, index -> element/address
        elif name == 'ldelema':
            if len(stack) >= 2:
                idx_desc, _, _ = stack.pop()
                arr_desc, _, _ = stack.pop()
                stack.append((f"&{arr_desc}[{idx_desc}]", addr, None))
        elif name in ('ldelem.i1', 'ldelem.u1', 'ldelem.i2', 'ldelem.u2',
                       'ldelem.i4', 'ldelem.u4', 'ldelem.i8', 'ldelem.ref'):
            if len(stack) >= 2:
                idx_desc, _, _ = stack.pop()
                arr_desc, _, _ = stack.pop()
                stack.append((f"{arr_desc}[{idx_desc}]", addr, None))

        # stind: addr, value
        elif name in ('stind.i1', 'stind.i2', 'stind.i4', 'stind.i8', 'stind.ref'):
            if len(stack) >= 2:
                val_desc, val_addr, val_const = stack.pop()
                addr_desc, addr_addr, _ = stack.pop()
                stores.append({
                    'addr': addr,
                    'elem_type': f'stind.{name.split(".")[-1]}',
                    'array': f'*({addr_desc})',
                    'array_addr': addr_addr,
                    'index': '*',
                    'index_addr': addr,
                    'index_const': None,
                    'value': val_desc,
                    'value_addr': val_addr,
                    'value_const': val_const,
                })

        # stloc
        elif name in ('stloc.0', 'stloc.1', 'stloc.2', 'stloc.3'):
            if stack:
                v, o, c = stack.pop()
                stack.append((f"loc{int(name[-1])}={v}", addr, c))
        elif name == 'stloc.s':
            if stack:
                v, o, c = stack.pop()
                stack.append((f"loc{op_val}={v}", addr, c))

        # pop
        elif name == 'pop':
            if stack:
                stack.pop()

        # Branches - pop condition for brtrue/brfalse
        elif name in ('brfalse', 'brtrue', 'brfalse.s', 'brtrue.s',
                       'beq', 'beq.s', 'bge', 'bge.s', 'bgt', 'bgt.s',
                       'ble', 'ble.s', 'blt', 'blt.s',
                       'bne.un', 'bne.un.s', 'bge.un', 'bge.un.s',
                       'bgt.un', 'bgt.un.s', 'ble.un', 'ble.un.s',
                       'blt.un', 'blt.un.s'):
            if len(stack) >= 2 and ('eq' in name or 'ge' in name or 'gt' in name or 'le' in name or 'lt' in name or 'ne' in name):
                stack.pop()  # pop two for comparison branches
                stack.pop()
            elif stack:
                stack.pop()  # pop one for brtrue/brfalse

        # newobj
        elif name == 'newobj':
            stack.append((f"new({resolver.resolve(op_val)})", addr, None))

        # ldstr
        elif name == 'ldstr':
            stack.append((f"str", addr, None))

        # ldnull
        elif name == 'ldnull':
            stack.append(("null", addr, None))

        # box
        elif name == 'box':
            if stack:
                v, o, c = stack.pop()
                stack.append((f"box({v})", o, c))

        # calls - pop args, push result (simplified)
        elif 'call' in name:
            # Simplified: just pop all args we can track and push result
            pass

        # ret
        elif name == 'ret':
            pass

        # castclass/isinst
        elif name in ('castclass', 'isinst'):
            if stack:
                v, o, c = stack.pop()
                stack.append((f"cast({v})", o, c))

        # initobj - pops address
        elif name == 'initobj':
            if stack:
                stack.pop()

    return stores


# ============================================================
# Main
# ============================================================

def main():
    exe_path = EXE_PATH
    if not exe_path.exists():
        print(f"ERROR: {exe_path} not found")
        sys.exit(1)

    print(f"[*] Loading {exe_path}")
    pe = PEFile(str(exe_path))
    resolver = TokenResolver(str(exe_path))

    # Find method
    method_idx, method_name, rva = None, None, None
    for i, m in enumerate(resolver.method_table):
        name = resolver.get_string(m.Name)
        if 'onGetPcInfoOk' in name:
            method_idx, method_name, rva = i + 1, name, m.Rva
            break

    if method_idx is None:
        print("ERROR: onGetPcInfoOk not found")
        sys.exit(1)

    print(f"[+] Method: {method_name} (index={method_idx}, RVA=0x{rva:x})")

    # Read IL body
    file_offset = pe.rva_to_offset(rva)
    if file_offset is None:
        print(f"ERROR: RVA 0x{rva:x} not in any section")
        sys.exit(1)

    raw = pe.data[file_offset:file_offset + 20000]

    # Parse header
    flags = read_u16(raw, 0)
    is_fat = flags & 0x0003
    if is_fat:
        header_units = (flags >> 12) & 0xF
        header_size = max(header_units, 3) * 4
        max_stack = read_u16(raw, 2)
        code_size = read_u32(raw, 4)
        local_sig = read_u32(raw, 8)
        code_offset = header_size
        print(f"    Fat header: size={header_size}, max_stack={max_stack}, code_size={code_size}, local_sig=0x{local_sig:x}")
    else:
        code_size = flags >> 2
        code_offset = 1
        print(f"    Tiny header: code_size={code_size}")

    code = raw[code_offset:code_offset + code_size]
    print(f"    Code bytes: {len(code)}")
    print()

    # ======== RAW HEX DUMP ========
    print("=" * 80)
    print("RAW IL HEX DUMP")
    print("=" * 80)
    for i in range(0, min(len(code), 512), 16):
        chunk = code[i:i+16]
        hexstr = ' '.join(f'{b:02x}' for b in chunk)
        print(f"  IL_{i:04x}: {hexstr}")
    if len(code) > 512:
        print(f"  ... ({len(code)} bytes total)")
    print()

    # ======== FULL DISASSEMBLY ========
    print("=" * 80)
    print("FULL DISASSEMBLY (first 1500 bytes)")
    print("=" * 80)
    instructions = disassemble(code, resolver)

    # Only print first portion to keep output manageable
    last_printed_addr = 0
    for addr, mnemonic, op_disp, op_val in instructions:
        if addr > 1500:
            break
        last_printed_addr = addr

        # Format branch targets
        display = op_disp
        if mnemonic in ('br.s', 'brfalse.s', 'brtrue.s', 'beq.s', 'bge.s', 'bgt.s',
                         'ble.s', 'blt.s', 'bne.un.s', 'bge.un.s', 'bgt.un.s',
                         'ble.un.s', 'blt.un.s',
                         'br', 'brfalse', 'brtrue', 'beq', 'bge', 'bgt',
                         'ble', 'blt', 'bne.un', 'bge.un', 'bgt.un',
                         'ble.un', 'blt.un'):
            target = addr + (1 if mnemonic.endswith('.s') else 5) + op_val
            display = f"IL_{target:04x}"
        elif mnemonic == 'leave.s':
            target = addr + 2 + op_val
            display = f"IL_{target:04x}"
        elif mnemonic == 'leave':
            target = addr + 5 + op_val
            display = f"IL_{target:04x}"

        print(f"  IL_{addr:04x}: {mnemonic:20s} {display}")

    print(f"  ... (truncated, showing {last_printed_addr} of {len(code)} bytes)")
    print()

    # ======== STELEM ANALYSIS ========
    print("=" * 80)
    print("FRAME BYTE STORE ANALYSIS (all array/field stores)")
    print("=" * 80)
    stores = trace_stores(code, resolver)
    for s in stores:
        idx_str = s['index']
        if s['index_const'] is not None:
            idx_str += f" == {s['index_const']}"
        val_str = s['value']
        if s['value_const'] is not None:
            val_str += f" == {s['value_const']}"

        print(f"  IL_{s['addr']:04x}: [{s['elem_type']:12s}] {s['array']}[{idx_str}] = {val_str}")
    print()

    # ======== FRAME MAP TABLE ========
    print("=" * 80)
    print("INFERRED FRAME BYTE MAP (looking for byte[] array patterns)")
    print("=" * 80)

    # Filter to only stores into what looks like the main byte array
    frame_stores = []
    for s in stores:
        if s['index_const'] is not None and s['elem_type'] in ('i1', 'i2', 'i4', 'u1', 'u2', 'u4'):
            frame_stores.append(s)
        elif s['elem_type'] == 'field':
            frame_stores.append(s)

    frame_stores.sort(key=lambda x: x['index_const'] if x['index_const'] is not None else 9999)

    for s in frame_stores:
        idx = s['index_const'] if s['index_const'] is not None else s['index']
        val = s['value_const'] if s['value_const'] is not None else s['value']
        elem = s['elem_type']
        print(f"  frame[{idx:3}] = {val}  (store type: {elem}, at IL_{s['addr']:04x})")

    print()
    print("=" * 80)
    print("DONE")
    print("=" * 80)


if __name__ == '__main__':
    main()

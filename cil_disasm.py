#!/usr/bin/env python3
"""
CIL IL Disassembler for PcInfoMonitorPro.exe
Parses .NET metadata, resolves tokens, and disassembles method bodies.
"""

import struct
import sys
import os
from pathlib import Path

EXE_PATH = Path(__file__).parent / "WALRUS_inno_extracted" / "app" / "PcInfoMonitorPro.exe"


def read_u16(data, offset):
    return struct.unpack_from('<H', data, offset)[0]

def read_u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]

def read_u64(data, offset):
    return struct.unpack_from('<Q', data, offset)[0]

def read_u8(data, offset):
    return data[offset]

def read_i8(data, offset):
    return struct.unpack_from('<b', data, offset)[0]

def read_i16(data, offset):
    return struct.unpack_from('<h', data, offset)[0]

def read_i32(data, offset):
    return struct.unpack_from('<i', data, offset)[0]

# ============================================================
# PE Parser
# ============================================================
class PEFile:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        
        # DOS header
        self.dos_e_lfanew = read_u32(self.data, 0x3C)
        
        # PE signature
        assert self.data[self.dos_e_lfanew:self.dos_e_lfanew+4] == b'PE\x00\x00'
        pe_offset = self.dos_e_lfanew + 4
        
        # COFF header
        self.num_sections = read_u16(self.data, pe_offset + 2)
        self.size_opt_header = read_u16(self.data, pe_offset + 16)
        self.opt_header_offset = pe_offset + 20
        
        # Optional header
        magic = read_u16(self.data, self.opt_header_offset)
        if magic == 0x10b:  # PE32
            self.image_base = read_u32(self.data, self.opt_header_offset + 28)
        else:  # PE32+
            self.image_base = read_u64(self.data, self.opt_header_offset + 24)
        
        # Section headers
        sec_offset = self.opt_header_offset + self.size_opt_header
        self.sections = []
        for i in range(self.num_sections):
            off = sec_offset + i * 40
            name = self.data[off:off+8].rstrip(b'\x00').decode('ascii', errors='replace')
            vsize = read_u32(self.data, off + 8)
            va = read_u32(self.data, off + 12)
            raw_size = read_u32(self.data, off + 16)
            raw_ptr = read_u32(self.data, off + 20)
            self.sections.append({
                'name': name, 'va': va, 'raw_ptr': raw_ptr,
                'raw_size': raw_size, 'vsize': vsize
            })
    
    def va_to_offset(self, va):
        """Convert Virtual Address to file offset"""
        for sec in self.sections:
            if sec['va'] <= va < sec['va'] + sec['vsize']:
                return va - sec['va'] + sec['raw_ptr']
        return None
    
    def rva_to_offset(self, rva):
        return self.va_to_offset(rva)
    
    def read_rva(self, rva, size):
        off = self.rva_to_offset(rva)
        if off is None:
            return None
        return self.data[off:off+size]


# ============================================================
# .NET Metadata Parser
# ============================================================
class DotNetMetadata:
    def __init__(self, pe):
        self.pe = pe
        self.streams = {}
        self.tables = {}
        self.metadata_root = None
        
    def find_metadata_root(self):
        """Find BSJB signature"""
        data = self.pe.data
        idx = data.find(b'BSJB')
        if idx == -1:
            raise ValueError("BSJB signature not found")
        self.metadata_root = idx
        return idx
    
    def parse_streams(self):
        """Parse #~, #Strings, #US, #GUID, #Blob streams"""
        idx = self.metadata_root
        # Skip signature (4 bytes) + version length (4 bytes)
        version_len = read_u32(self.pe.data, idx + 8)
        version_offset = idx + 12 + version_len
        # Align to 4 bytes
        if version_offset % 4:
            version_offset += 4 - (version_offset % 4)
        
        num_streams = read_u16(self.pe.data, version_offset)
        off = version_offset + 2
        
        for _ in range(num_streams):
            s_offset = read_u32(self.pe.data, off)
            s_size = read_u32(self.pe.data, off + 4)
            off += 8
            # Read null-terminated name
            name_start = off
            while self.pe.data[off] != 0:
                off += 1
            name = self.pe.data[name_start:off].decode('ascii')
            off += 1  # skip null
            # Align to 4 bytes
            if off % 4:
                off += 4 - (off % 4)
            
            abs_offset = self.metadata_root + s_offset
            self.streams[name] = {
                'offset': abs_offset,
                'size': s_size,
                'data': self.pe.data[abs_offset:abs_offset + s_size]
            }
    
    def read_string(self, idx):
        """Read null-terminated string from #Strings stream"""
        if '#Strings' not in self.streams:
            return f"<no_strings_stream>"
        data = self.streams['#Strings']['data']
        if idx >= len(data):
            return f"<out_of_range:{idx}>"
        end = data.index(b'\x00', idx)
        return data[idx:end].decode('utf-8', errors='replace')
    
    def read_user_string(self, idx):
        """Read UTF-16 string from #US stream"""
        if '#US' not in self.streams:
            return "<no_us_stream>"
        data = self.streams['#US']['data']
        if idx >= len(data):
            return f"<out_of_range_us:{idx}>"
        # US strings are length-prefixed with compressed integer
        b0 = data[idx]
        if b0 & 0x80 == 0:
            length = b0
            idx += 1
        elif b0 & 0xC0 == 0x80:
            length = ((b0 & 0x3F) << 8) | data[idx+1]
            idx += 2
        elif b0 & 0xE0 == 0xC0:
            length = ((b0 & 0x1F) << 24) | (data[idx+1] << 16) | (data[idx+2] << 8) | data[idx+3]
            idx += 4
        else:
            return f"<bad_us_len>"
        raw = data[idx:idx+length]
        # Remove trailing null byte
        if raw.endswith(b'\x00'):
            raw = raw[:-1]
        try:
            return raw.decode('utf-16-le')
        except:
            return repr(raw)
    
    def read_blob(self, idx):
        """Read blob entry from #Blob stream"""
        if '#Blob' not in self.streams:
            return b''
        data = self.streams['#Blob']['data']
        if idx >= len(data):
            return b''
        b0 = data[idx]
        if b0 & 0x80 == 0:
            length = b0
            idx += 1
        elif b0 & 0xC0 == 0x80:
            length = ((b0 & 0x3F) << 8) | data[idx+1]
            idx += 2
        elif b0 & 0xE0 == 0xC0:
            length = ((b0 & 0x1F) << 24) | (data[idx+1] << 16) | (data[idx+2] << 8) | data[idx+3]
            idx += 4
        else:
            return b''
        return data[idx:idx+length]

    def parse_tables(self):
        """Parse metadata tables from #~ stream"""
        if '#~' not in self.streams:
            raise ValueError("No #~ stream")
        
        data = self.streams['#~']['data']
        
        # Reserved (4), MajorVersion (1), MinorVersion (1), HeapSizes (1), Reserved (1)
        # TableBitmap (8), ValidTables (8)
        heap_sizes = data[6]
        self.heap_sizes = heap_sizes
        
        string_idx_size = 4 if (heap_sizes & 0x01) else 2
        guid_idx_size = 4 if (heap_sizes & 0x02) else 2
        blob_idx_size = 4 if (heap_sizes & 0x04) else 2
        
        self.string_idx_size = string_idx_size
        self.guid_idx_size = guid_idx_size
        self.blob_idx_size = blob_idx_size
        
        # Valid tables bitmask (8 bytes)
        valid = struct.unpack_from('<Q', data, 8)[0]
        
        # Number of rows for each present table
        row_counts = []
        offset = 16
        for i in range(64):
            if valid & (1 << i):
                row_counts.append((i, read_u32(data, offset)))
                offset += 4
            else:
                row_counts.append((i, 0))
        
        # Table row sizes (simplified)
        self.table_rows = {}
        self.table_names = [
            'Module', 'TypeRef', 'TypeDef', 'FieldPtr', 'Field', 'MethodPtr',
            'Method', 'ParamPtr', 'Param', 'InterfaceImpl', 'MemberRef',
            'Constant', 'CustomAttribute', 'FieldMarshal', 'DeclSecurity',
            'ClassLayout', 'FieldLayout', 'StandAloneSig', 'EventMap',
            'EventPtr', 'Event', 'PropertyMap', 'PropertyPtr', 'Property',
            'MethodSemantics', 'MethodImpl', 'ModuleRef', 'TypeSpec',
            'ImplMap', 'FieldRVA', 'Unused6', 'Unused7', 'Assembly',
            'AssemblyProcessor', 'AssemblyOS', 'AssemblyRef',
            'AssemblyRefProcessor', 'AssemblyRefOS', 'File',
            'ExportedType', 'ManifestResource', 'NestedClass',
            'GenericParam', 'MethodSpec', 'GenericParamConstraint'
        ]
        
        # Store row offsets
        self.table_row_offsets = {}
        self.table_row_counts = {}
        cur_offset = offset
        
        for i, (table_idx, count) in enumerate(row_counts):
            if count > 0:
                self.table_row_offsets[table_idx] = cur_offset
                self.table_row_counts[table_idx] = count
                cur_offset += count * self._table_row_size(table_idx, heap_sizes, row_counts)
        
        self.table_data = data
        self.row_counts_raw = row_counts
    
    def _table_row_size(self, table_idx, heap_sizes, row_counts):
        """Calculate row size for a given table"""
        s = self.string_idx_size
        g = self.guid_idx_size
        b = self.blob_idx_size
        
        # Simplified table row sizes
        sizes = {
            0x00: 2 + s + g + b,  # Module
            0x01: 1 + s + s + s,  # TypeRef
            0x02: 4 + s + s + 4 + 4,  # TypeDef
            0x04: 2 + 1 + s + b,  # Field
            0x06: 4 + 2 + 2 + s + b,  # Method
            0x08: 2 + 2 + s,  # Param
            0x09: 4 + 4,  # InterfaceImpl
            0x0A: 4 + 4 + s + b,  # MemberRef
            0x0C: 4 + 1 + b,  # Constant
            0x0D: 4 + 4 + b,  # CustomAttribute
            0x0E: 4 + 4 + b,  # FieldMarshal
            0x10: 2 + 2 + 4 + s,  # ClassLayout
            0x11: 4 + 4,  # FieldLayout
            0x12: 4,  # StandAloneSig
            0x15: 4 + 4,  # MethodSemantics
            0x16: 4 + 4 + 4,  # MethodImpl
            0x17: 2 + s + s + s,  # ModuleRef
            0x1B: 4,  # ImplMap
            0x1C: 4 + 4,  # FieldRVA
            0x20: 4 + 4 + s + s + s + b,  # Assembly
            0x26: 2 + 2 + 4 + s + s + b,  # AssemblyRef
            0x27: 4 + 4 + 4,  # AssemblyRefProcessor
            0x28: 4 + s + s + 4 + 4,  # AssemblyRefOS
            0x2A: 4 + 4 + 4,  # File
            0x2B: 4 + 4 + 4 + s,  # ExportedType
            0x2C: 4 + 4 + s,  # ManifestResource
            0x2D: 4 + 4,  # NestedClass
            0x2E: 2 + 2 + 1 + s,  # GenericParam
            0x2F: 4 + 2 + b,  # MethodSpec
            0x30: 4 + 4,  # GenericParamConstraint
        }
        
        # For tables with pointer columns, we need to compute
        if table_idx not in sizes:
            return 0
        
        return sizes[table_idx]
    
    def _idx_size(self, table_idx, row_counts):
        """Get index size for a table reference"""
        if row_counts[table_idx][1] <= 0xFF:
            return 1
        elif row_counts[table_idx][1] <= 0xFFFF:
            return 2
        else:
            return 4
    
    def _coded_index_size(self, coding_tag, row_counts):
        """Get coded index size"""
        max_rows = 0
        for table_idx in coding_tag:
            if table_idx < len(row_counts):
                max_rows = max(max_rows, row_counts[table_idx][1])
        # Number of tags
        num_tags = len(coding_tag)
        bits_needed = (num_tags - 1).bit_length()
        
        if max_rows <= (0xFF >> bits_needed):
            return 1
        elif max_rows <= (0xFFFF >> bits_needed):
            return 2
        else:
            return 4
    
    def read_table_raw(self, table_idx, row_num):
        """Read raw row bytes from table"""
        if table_idx not in self.table_row_offsets:
            return None
        offset = self.table_row_offsets[table_idx]
        row_size = self._table_row_size(table_idx, self.heap_sizes, self.row_counts_raw)
        return self.table_data[offset + row_num * row_size : offset + (row_num + 1) * row_size]


# ============================================================
# .NET Metadata reader using dnfile for easier parsing
# ============================================================
class DotNetReader:
    def __init__(self, path):
        import dnfile
        self.path = path
        self.dn = dnfile.dnPE(str(path))
        self.exe_data = None
        with open(path, 'rb') as f:
            self.exe_data = f.read()
        
        self.md = self.dn.net
        if self.md is None:
            raise ValueError("No .NET metadata found")
        
        self.mdtables = self.md.TableStream
        self.strings = self.md.StringsStream
        self.blobs = self.md.BlobStream
        self.us = self.md.UserStringStream
        self.guids = self.md.GUIDStream
        
        # Cache tables
        self.method_table = list(self.mdtables.MethodDef) if self.mdtables.MethodDef else []
        self.typedef_table = list(self.mdtables.TypeDef) if self.mdtables.TypeDef else []
        self.field_table = list(self.mdtables.Field) if self.mdtables.Field else []
        self.memberref_table = list(self.mdtables.MemberRef) if self.mdtables.MemberRef else []
        self.typeref_table = list(self.mdtables.TypeRef) if self.mdtables.TypeRef else []
        self.fieldrva_table = list(self.mdtables.FieldRVA) if self.mdtables.FieldRVA else []
        self.codedindex = self.md.CodedIndex if hasattr(self.md, 'CodedIndex') else None
    
    def get_string(self, idx):
        if self.strings and idx is not None:
            try:
                return self.strings.get_at(idx)
            except:
                return f"<str_err:{idx}>"
        return f"<no_str:{idx}>"
    
    def get_blob(self, idx):
        if self.blobs and idx is not None:
            try:
                return self.blobs.get_at(idx)
            except:
                return b''
        return b''
    
    def get_us(self, idx):
        if self.us and idx is not None:
            try:
                return self.us.get_at(idx)
            except:
                return f"<us_err:{idx}>"
        return f"<no_us:{idx}>"
    
    def get_method_def(self, idx):
        """Get MethodDef by 1-based row index"""
        if 1 <= idx <= len(self.method_table):
            return self.method_table[idx - 1]
        return None
    
    def get_typedef(self, idx):
        if 1 <= idx <= len(self.typedef_table):
            return self.typedef_table[idx - 1]
        return None
    
    def get_typeref(self, idx):
        if 1 <= idx <= len(self.typeref_table):
            return self.typeref_table[idx - 1]
        return None
    
    def get_memberref(self, idx):
        if 1 <= idx <= len(self.memberref_table):
            return self.memberref_table[idx - 1]
        return None
    
    def get_field(self, idx):
        if 1 <= idx <= len(self.field_table):
            return self.field_table[idx - 1]
        return None
    
    def resolve_token(self, token):
        """Resolve a metadata token to a human-readable string"""
        if token == 0:
            return "<null>"
        
        table = (token >> 24) & 0xFF
        row = token & 0xFFFFFF
        
        if table == 0x06:  # MethodDef
            m = self.get_method_def(row)
            if m:
                # Get the owning type
                type_name = self.get_method_owner_type_name(row)
                method_name = self.get_string(m.Name)
                return f"{type_name}::{method_name}"
            return f"MethodDef[{row}]"
        
        elif table == 0x04:  # Field
            f = self.get_field(row)
            if f:
                return self.get_string(f.Name)
            return f"Field[{row}]"
        
        elif table == 0x01:  # TypeRef
            t = self.get_typeref(row)
            if t:
                ns = self.get_string(t.TypeNamespace)
                nm = self.get_string(t.TypeName)
                if ns:
                    return f"{ns}.{nm}"
                return nm
            return f"TypeRef[{row}]"
        
        elif table == 0x0A:  # MemberRef
            mr = self.get_memberref(row)
            if mr:
                try:
                    name = self.get_string(mr.Name)
                    # Try to get the class
                    cls = mr.Class
                    if hasattr(cls, 'row_index'):
                        cls_idx = cls.row_index
                        cls_table = cls.table
                        if hasattr(cls_table, '__name__') and 'TypeRef' in str(type(cls_table)):
                            t = self.get_typeref(cls_idx)
                            if t:
                                ns = self.get_string(t.TypeNamespace)
                                nm = self.get_string(t.TypeName)
                                return f"{ns}.{nm}::{name}" if ns else f"{nm}::{name}"
                    return f"MemberRef::{name}"
                except:
                    return f"MemberRef[{row}]"
            return f"MemberRef[{row}]"
        
        elif table == 0x02:  # TypeDef
            t = self.get_typedef(row)
            if t:
                ns = self.get_string(t.TypeNamespace)
                nm = self.get_string(t.TypeName)
                return f"{ns}.{nm}" if ns else nm
            return f"TypeDef[{row}]"
        
        elif table == 0x1B:  # ModuleRef
            return f"ModuleRef[{row}]"
        
        elif table == 0x1C:  # TypeSpec
            return f"TypeSpec[{row}]"
        
        elif table == 0x08:  # String (user string #US)
            return f'"{self.get_us(row)}"'
        
        elif table == 0x1E:  # FieldRVA
            return f"FieldRVA[{row}]"
        
        return f"Token_{table:02X}_{row}"
    
    def get_method_owner_type_name(self, method_idx):
        """Find the owning TypeDef for a MethodDef row index"""
        for i, td in enumerate(self.typedef_table):
            try:
                first_method = td.FirstMethod.row_index if hasattr(td.FirstMethod, 'row_index') else td.FirstMethod
                # Next type's first method
                if i + 1 < len(self.typedef_table):
                    next_td = self.typedef_table[i + 1]
                    next_first = next_td.FirstMethod.row_index if hasattr(next_td.FirstMethod, 'row_index') else next_td.FirstMethod
                else:
                    next_first = len(self.method_table) + 1
                
                if first_method <= method_idx < next_first:
                    ns = self.get_string(td.TypeNamespace)
                    nm = self.get_string(td.TypeName)
                    return f"{ns}.{nm}" if ns else nm
            except:
                continue
        return "<unknown_type>"
    
    def find_methods_by_name(self, search_name):
        """Find all methods containing search_name in their name"""
        results = []
        for i, m in enumerate(self.method_table):
            name = self.get_string(m.Name)
            if search_name.lower() in name.lower():
                type_name = self.get_method_owner_type_name(i + 1)
                rva = m.Rva
                results.append({
                    'index': i + 1,
                    'name': name,
                    'type': type_name,
                    'rva': rva,
                    'flags': m.Flags,
                    'impl_flags': m.ImplFlags,
                    'signature': self.get_blob(m.Signature),
                })
        return results
    
    def find_methods_by_type(self, type_search):
        """Find all methods belonging to a type matching type_search"""
        results = []
        for i, td in enumerate(self.typedef_table):
            ns = self.get_string(td.TypeNamespace)
            nm = self.get_string(td.TypeName)
            full_name = f"{ns}.{nm}" if ns else nm
            if type_search.lower() in full_name.lower():
                first_method = td.FirstMethod.row_index if hasattr(td.FirstMethod, 'row_index') else td.FirstMethod
                if i + 1 < len(self.typedef_table):
                    next_td = self.typedef_table[i + 1]
                    next_first = next_td.FirstMethod.row_index if hasattr(next_td.FirstMethod, 'row_index') else next_td.FirstMethod
                else:
                    next_first = len(self.method_table) + 1
                
                for j in range(first_method - 1, next_first - 1):
                    if j < len(self.method_table):
                        m = self.method_table[j]
                        name = self.get_string(m.Name)
                        results.append({
                            'index': j + 1,
                            'name': name,
                            'type': full_name,
                            'rva': m.Rva,
                            'flags': m.Flags,
                            'impl_flags': m.ImplFlags,
                            'signature': self.get_blob(m.Signature),
                        })
        return results
    
    def find_fields_by_type(self, type_search):
        """Find all fields belonging to a type matching type_search"""
        results = []
        for i, td in enumerate(self.typedef_table):
            ns = self.get_string(td.TypeNamespace)
            nm = self.get_string(td.TypeName)
            full_name = f"{ns}.{nm}" if ns else nm
            if type_search.lower() in full_name.lower():
                first_field = td.FirstField.row_index if hasattr(td.FirstField, 'row_index') else td.FirstField
                if i + 1 < len(self.typedef_table):
                    next_td = self.typedef_table[i + 1]
                    next_first = next_td.FirstField.row_index if hasattr(next_td.FirstField, 'row_index') else next_td.FirstField
                else:
                    next_first = len(self.field_table) + 1
                
                for j in range(first_field - 1, next_first - 1):
                    if j < len(self.field_table):
                        f = self.field_table[j]
                        name = self.get_string(f.Name)
                        results.append({
                            'index': j + 1,
                            'name': name,
                            'type': full_name,
                        })
        return results
    
    def list_all_types(self):
        """List all TypeDefs with their namespace and name"""
        results = []
        for i, td in enumerate(self.typedef_table):
            ns = self.get_string(td.TypeNamespace)
            nm = self.get_string(td.TypeName)
            full_name = f"{ns}.{nm}" if ns else nm
            results.append((i + 1, full_name))
        return results


# ============================================================
# CIL Disassembler
# ============================================================

# CIL opcode tables (simplified - covers the most common opcodes)
OPCODES = {
    0x00: ('nop', 0),
    0x01: ('break', 0),
    0x02: ('ldarg.0', 0),
    0x03: ('ldarg.1', 0),
    0x04: ('ldarg.2', 0),
    0x05: ('ldarg.3', 0),
    0x06: ('ldarg.s', 1),      # uint8
    0x07: ('ldarg', 2),         # uint16 (actually int16)
    0x09: ('ldarga.s', 1),
    0x0A: ('ldnull', 0),
    0x0B: ('ldc.i4.m1', 0),
    0x0C: ('ldc.i4.0', 0),
    0x0D: ('ldc.i4.1', 0),
    0x0E: ('ldc.i4.2', 0),
    0x0F: ('ldc.i4.3', 0),
    0x10: ('ldc.i4.4', 0),
    0x11: ('ldc.i4.5', 0),
    0x12: ('ldc.i4.6', 0),
    0x13: ('ldc.i4.7', 0),
    0x14: ('ldc.i4.8', 0),
    0x15: ('ldc.i4.s', 1),     # int8
    0x16: ('ldc.i4', 4),        # int32
    0x17: ('ldc.i8', 8),        # int64
    0x18: ('ldc.r4', 4),        # float32
    0x19: ('ldc.r8', 8),        # float64
    0x1A: ('dup', 0),
    0x1B: ('pop', 0),
    0x1C: ('jmp', 4),           # token
    0x1D: ('call', 4),          # token
    0x1E: ('calli', 4),         # token
    0x1F: ('ret', 0),
    0x20: ('br.s', 1),          # int8 offset
    0x21: ('brfalse.s', 1),
    0x22: ('brtrue.s', 1),
    0x23: ('beq.s', 1),
    0x24: ('bge.s', 1),
    0x25: ('bgt.s', 1),
    0x26: ('ble.s', 1),
    0x27: ('blt.s', 1),
    0x28: ('bne.un.s', 1),
    0x29: ('bge.un.s', 1),
    0x2A: ('bgt.un.s', 1),
    0x2B: ('ble.un.s', 1),
    0x2C: ('blt.un.s', 1),
    0x2D: ('switch', None),     # variable: count(4) + offsets(count*4)
    0x2E: ('ldind.i1', 0),
    0x2F: ('ldind.u1', 0),
    0x30: ('ldind.i2', 0),
    0x31: ('ldind.u2', 0),
    0x32: ('ldind.i4', 0),
    0x33: ('ldind.u4', 0),
    0x34: ('ldind.i8', 0),
    0x35: ('ldind.r4', 0),
    0x36: ('ldind.r8', 0),
    0x37: ('ldind.ref', 0),
    0x38: ('stind.ref', 0),
    0x39: ('stind.i1', 0),
    0x3A: ('stind.i2', 0),
    0x3B: ('stind.i4', 0),
    0x3C: ('stind.i8', 0),
    0x3D: ('stind.r4', 0),
    0x3E: ('stind.r8', 0),
    0x3F: ('add', 0),
    0x40: ('sub', 0),
    0x41: ('mul', 0),
    0x42: ('div', 0),
    0x43: ('div.un', 0),
    0x44: ('rem', 0),
    0x45: ('rem.un', 0),
    0x46: ('and', 0),
    0x47: ('or', 0),
    0x48: ('xor', 0),
    0x49: ('shl', 0),
    0x4B: ('shr', 0),
    0x4C: ('shr.un', 0),
    0x4D: ('neg', 0),
    0x4E: ('not', 0),
    0x4F: ('conv.i1', 0),
    0x50: ('conv.i2', 0),
    0x51: ('conv.i4', 0),
    0x52: ('conv.i8', 0),
    0x53: ('conv.r4', 0),
    0x54: ('conv.r8', 0),
    0x55: ('conv.u4', 0),
    0x56: ('conv.u8', 0),
    0x58: ('callvirt', 4),
    0x59: ('cpobj', 4),
    0x5A: ('ldobj', 4),
    0x5B: ('ldstr', 4),
    0x5C: ('newobj', 4),
    0x5D: ('castclass', 4),
    0x5E: ('isinst', 4),
    0x5F: ('conv.r.un', 0),
    0x62: ('throw', 0),
    0x63: ('ldfld', 4),
    0x64: ('ldflda', 4),
    0x65: ('stfld', 4),
    0x66: ('ldsfld', 4),
    0x67: ('ldsflda', 4),
    0x68: ('stsfld', 4),
    0x69: ('stobj', 4),
    0x6A: ('ldstr', 4),  # duplicate - check
    0x6B: ('newarr', 4),
    0x6C: ('ldlen', 0),
    0x6D: ('ldelema', 4),
    0x6E: ('ldelem.i1', 0),
    0x6F: ('ldelem.u1', 0),
    0x70: ('ldelem.i2', 0),
    0x71: ('ldelem.u2', 0),
    0x72: ('ldelem.i4', 0),
    0x73: ('ldelem.u4', 0),
    0x74: ('ldelem.i8', 0),
    0x75: ('ldelem.r4', 0),
    0x76: ('ldelem.r8', 0),
    0x77: ('ldelem.ref', 0),
    0x78: ('stelem.i', 0),
    0x79: ('stelem.i1', 0),
    0x7A: ('stelem.i2', 0),
    0x7B: ('stelem.i4', 0),
    0x7C: ('stelem.i8', 0),
    0x7D: ('stelem.r4', 0),
    0x7E: ('stelem.r8', 0),
    0x7F: ('stelem.ref', 0),
    0x80: ('stelem.ref', 0),  # need to check
    0x8C: ('box', 4),
    0x8D: ('newarr', 4),
    0x74: ('ldelem.ref', 0),  # wrong, fix
    0x75: ('ldelem.r4', 0),
    0x76: ('ldelem.r8', 0),
    0x77: ('ldelem.ref', 0),
    0x78: ('stelem.i', 0),
    0x79: ('stelem.i1', 0),
    0x7A: ('stelem.i2', 0),
    0x7B: ('stelem.i4', 0),
    0x7C: ('stelem.i8', 0),
    0x7D: ('stelem.r4', 0),
    0x7E: ('stelem.r8', 0),
    0x7F: ('stelem.ref', 0),
    0x8C: ('box', 4),
    0x8D: ('newarr', 4),
    0x8E: ('ldlen', 0),
    0x8F: ('ldelema', 4),
    0x90: ('ldelem.i1', 0),
    0x91: ('ldelem.u1', 0),
    0x92: ('ldelem.i2', 0),
    0x93: ('ldelem.u2', 0),
    0x94: ('ldelem.i4', 0),
    0x95: ('ldelem.u4', 0),
    0x96: ('ldelem.i8', 0),
    0x97: ('ldelem.r4', 0),
    0x98: ('ldelem.r8', 0),
    0x99: ('ldelem.ref', 0),
    0x9A: ('stelem.ref', 0),
    0x9B: ('stelem.i', 0),
    0x9C: ('stelem.i1', 0),
    0x9D: ('stelem.i2', 0),
    0x9E: ('stelem.i4', 0),
    0x9F: ('stelem.i8', 0),
    0xA0: ('stelem.r4', 0),
    0xA1: ('stelem.r8', 0),
    0xA2: ('stelem.ref', 0),
    0xA3: ('ldelem.ref', 0),
    0xA4: ('stelem.ref', 0),
    0xA5: ('stelem.i', 0),
    0xA6: ('stelem.i1', 0),
    0xA7: ('stelem.i2', 0),
    0xA8: ('stelem.i4', 0),
    0xA9: ('stelem.i8', 0),
    0xAA: ('stelem.r4', 0),
    0xAB: ('stelem.r8', 0),
    0xAC: ('stelem.ref', 0),
    0xAD: ('throw.any', 0),
    0xB3: ('refanytype', 0),
    0xB4: ('readonly.', 0),
    0xC2: ('tail.', 0),
    0xC3: ('initobj', 4),
    0xC4: ('constrained.', 4),
    0xC5: ('cpblk', 0),
    0xC6: ('initblk', 0),
    0xC7: ('no.', 1),
    0xC8: ('rethrow', 0),
    0xCC: ('sizeof', 4),
    0xD0: ('ldftn', 4),
    0xD1: ('ldvirtftn', 4),
    0xD3: ('ldarg', 2),
    0xD4: ('ldarga', 2),
    0xD5: ('starg', 2),
    0xD6: ('ldloc', 2),
    0xD7: ('ldloca', 2),
    0xD8: ('stloc', 2),
    0xD9: ('localloc', 0),
    0xDB: ('endfilter', 0),
    0xDC: ('unaligned.', 1),
    0xDD: ('volatile.', 0),
    0xDE: ('unaligned.', 1),
    0xDF: ('volatile.', 0),
    0xE0: ('ldfld', 4),
    0xE1: ('ldflda', 4),
    0xE2: ('stfld', 4),
    0xE3: ('ldsfld', 4),
    0xE4: ('ldsflda', 4),
    0xE5: ('stsfld', 4),
    0xE6: ('ldobj', 4),
    0xE7: ('stobj', 4),
    0xE8: ('box', 4),
    0xE9: ('newarr', 4),
    0xEA: ('ldlen', 0),
    0xEB: ('ldelema', 4),
    0xEC: ('ldelem.i1', 0),
    0xED: ('ldelem.u1', 0),
    0xEE: ('ldelem.i2', 0),
    0xEF: ('ldelem.u2', 0),
    0xF0: ('ldelem.i4', 0),
    0xF1: ('ldelem.u4', 0),
    0xF2: ('ldelem.i8', 0),
    0xF3: ('ldelem.r4', 0),
    0xF4: ('ldelem.r8', 0),
    0xF5: ('ldelem.ref', 0),
    0xF6: ('stelem.i', 0),
    0xF7: ('stelem.i1', 0),
    0xF8: ('stelem.i2', 0),
    0xF9: ('stelem.i4', 0),
    0xFA: ('stelem.i8', 0),
    0xFB: ('stelem.r4', 0),
    0xFC: ('stelem.r8', 0),
    0xFD: ('stelem.ref', 0),
    0xFE: ('prefix', None),  # Two-byte prefix
}

# Two-byte opcodes (0xFE prefix)
TWO_BYTE_OPCODES = {
    0x01: ('ceq', 0),
    0x02: ('cgt', 0),
    0x03: ('cgt.un', 0),
    0x04: ('clt', 0),
    0x05: ('clt.un', 0),
    0x06: ('ldftn', 4),
    0x07: ('ldvirtftn', 4),
    0x0A: ('ldarg', 2),
    0x0B: ('ldarg.a', 2),
    0x0C: ('starg', 2),
    0x0D: ('ldloc', 2),
    0x0E: ('ldloc.a', 2),
    0x0F: ('stloc', 2),
    0x11: ('ldnull', 0),
    0x12: ('dup', 0),
    0x13: ('pop', 0),
    0x14: ('cpblk', 0),
    0x15: ('initblk', 0),
    0x16: ('no.', 1),
    0x17: ('rethrow', 0),
    0x19: ('sizeof', 4),
    0x1A: ('refanytype', 0),
    0x1B: ('readonly.', 0),
    0x1C: ('tok', 4),  # ldtoken
    0x20: ('ceq', 0),
    0x21: ('cgt', 0),
    0x22: ('cgt.un', 0),
    0x23: ('clt', 0),
    0x24: ('clt.un', 0),
    0x25: ('ceq.s', 1),
    0x26: ('cgt.s', 1),
    0x27: ('cgt.un.s', 1),
    0x2B: ('endfinally', 0),
    0x2C: ('leave', 4),
    0x2D: ('leave.s', 1),
    0x2E: ('stind.i', 0),
    0x2F: ('conv.u', 0),
    0x30: ('ceq', 0),
    0x31: ('cgt', 0),
    0x32: ('cgt.un', 0),
    0x33: ('clt', 0),
    0x34: ('clt.un', 0),
    0x35: ('ceq.s', 1),
    0x36: ('cgt.s', 1),
    0x37: ('cgt.un.s', 1),
    0x45: ('constrained.', 4),
    0x46: ('cpblk', 0),
    0x47: ('initblk', 0),
    0x48: ('no.', 1),
    0x49: ('rethrow', 0),
    0x51: ('ldlen', 0),
    0x52: ('newarr', 4),
    0x53: ('ldelema', 4),
    0x54: ('ldelem', 4),  # Fixed: ldelem takes a type token
    0x55: ('ldelem.i1', 0),
    0x56: ('ldelem.u1', 0),
    0x57: ('ldelem.i2', 0),
    0x58: ('ldelem.u2', 0),
    0x59: ('ldelem.i4', 0),
    0x5A: ('ldelem.u4', 0),
    0x5B: ('ldelem.i8', 0),
    0x5C: ('ldelem.r4', 0),
    0x5D: ('ldelem.r8', 0),
    0x5E: ('ldelem.ref', 0),
    0x5F: ('stelem', 4),
    0x60: ('stelem.i', 0),
    0x61: ('stelem.i1', 0),
    0x62: ('stelem.i2', 0),
    0x63: ('stelem.i4', 0),
    0x64: ('stelem.i8', 0),
    0x65: ('stelem.r4', 0),
    0x66: ('stelem.r8', 0),
    0x67: ('stelem.ref', 0),
    0x6C: ('box', 4),
    0x6D: ('newarr', 4),
    0x6E: ('ldlen', 0),
    0x6F: ('ldelema', 4),
    0x70: ('ldelem.i1', 0),
    0x71: ('ldelem.u1', 0),
    0x72: ('ldelem.i2', 0),
    0x73: ('ldelem.u2', 0),
    0x74: ('ldelem.i4', 0),
    0x75: ('ldelem.u4', 0),
    0x76: ('ldelem.i8', 0),
    0x77: ('ldelem.r4', 0),
    0x78: ('ldelem.r8', 0),
    0x79: ('ldelem.ref', 0),
    0x7A: ('stelem.i', 0),
    0x7B: ('stelem.i1', 0),
    0x7C: ('stelem.i2', 0),
    0x7D: ('stelem.i4', 0),
    0x7E: ('stelem.i8', 0),
    0x7F: ('stelem.r4', 0),
    0x80: ('stelem.r8', 0),
    0x81: ('stelem.ref', 0),
    0x82: ('castclass', 4),
    0x83: ('isinst', 4),
    0x84: ('conv.r.un', 0),
    0x85: ('unbox', 4),
    0x86: ('throw', 0),
    0x87: ('ldfld', 4),
    0x88: ('ldflda', 4),
    0x89: ('stfld', 4),
    0x8A: ('ldsfld', 4),
    0x8B: ('ldsflda', 4),
    0x8C: ('stsfld', 4),
    0x8D: ('stobj', 4),
    0x8E: ('box', 4),
    0x8F: ('newarr', 4),
    0x90: ('ldlen', 0),
    0x91: ('ldelema', 4),
    0x92: ('ldelem.i1', 0),
    0x93: ('ldelem.u1', 0),
    0x94: ('ldelem.i2', 0),
    0x95: ('ldelem.u2', 0),
    0x96: ('ldelem.i4', 0),
    0x97: ('ldelem.u4', 0),
    0x98: ('ldelem.i8', 0),
    0x99: ('ldelem.r4', 0),
    0x9A: ('ldelem.r8', 0),
    0x9B: ('ldelem.ref', 0),
    0x9C: ('stelem.i', 0),
    0x9D: ('stelem.i1', 0),
    0x9E: ('stelem.i2', 0),
    0x9F: ('stelem.i4', 0),
    0xA0: ('stelem.i8', 0),
    0xA1: ('stelem.r4', 0),
    0xA2: ('stelem.r8', 0),
    0xA3: ('stelem.ref', 0),
    0xA4: ('ldelem.ref', 0),
    0xA5: ('stelem.ref', 0),
    0xA6: ('stelem.i', 0),
    0xA7: ('stelem.i1', 0),
    0xA8: ('stelem.i2', 0),
    0xA9: ('stelem.i4', 0),
    0xAA: ('stelem.i8', 0),
    0xAB: ('stelem.r4', 0),
    0xAC: ('stelem.r8', 0),
    0xAD: ('stelem.ref', 0),
    0xB3: ('refanytype', 0),
    0xB4: ('readonly.', 0),
    0xC2: ('tail.', 0),
    0xC3: ('initobj', 4),
    0xC4: ('constrained.', 4),
    0xC5: ('cpblk', 0),
    0xC6: ('initblk', 0),
    0xC7: ('no.', 1),
    0xC8: ('rethrow', 0),
    0xCC: ('sizeof', 4),
    0xD0: ('ldftn', 4),
    0xD1: ('ldvirtftn', 4),
    0xD3: ('ldarg', 2),
    0xD4: ('ldarga', 2),
    0xD5: ('starg', 2),
    0xD6: ('ldloc', 2),
    0xD7: ('ldloca', 2),
    0xD8: ('stloc', 2),
    0xD9: ('localloc', 0),
    0xDB: ('endfilter', 0),
    0xDC: ('unaligned.', 1),
    0xDD: ('volatile.', 0),
    0xDE: ('unaligned.', 1),
    0xDF: ('volatile.', 0),
    0xE0: ('ldfld', 4),
    0xE1: ('ldflda', 4),
    0xE2: ('stfld', 4),
    0xE3: ('ldsfld', 4),
    0xE4: ('ldsflda', 4),
    0xE5: ('stsfld', 4),
    0xE6: ('ldobj', 4),
    0xE7: ('stobj', 4),
    0xE8: ('box', 4),
    0xE9: ('newarr', 4),
    0xEA: ('ldlen', 0),
    0xEB: ('ldelema', 4),
    0xEC: ('ldelem.i1', 0),
    0xED: ('ldelem.u1', 0),
    0xEE: ('ldelem.i2', 0),
    0xEF: ('ldelem.u2', 0),
    0xF0: ('ldelem.i4', 0),
    0xF1: ('ldelem.u4', 0),
    0xF2: ('ldelem.i8', 0),
    0xF3: ('ldelem.r4', 0),
    0xF4: ('ldelem.r8', 0),
    0xF5: ('ldelem.ref', 0),
    0xF6: ('stelem.i', 0),
    0xF7: ('stelem.i1', 0),
    0xF8: ('stelem.i2', 0),
    0xF9: ('stelem.i4', 0),
    0xFA: ('stelem.i8', 0),
    0xFB: ('stelem.r4', 0),
    0xFC: ('stelem.r8', 0),
    0xFD: ('stelem.ref', 0),
}


def get_opcode_info(opcode):
    """Get opcode name and operand size"""
    if opcode == 0xFE:
        return ('PREFIX', None)  # Handled specially
    if opcode in OPCODES:
        return OPCODES[opcode]
    return (f'unknown(0x{opcode:02x})', 0)

def get_two_byte_opcode_info(opcode2):
    if opcode2 in TWO_BYTE_OPCODES:
        return TWO_BYTE_OPCODES[opcode2]
    return (f'unknown2(0xFE 0x{opcode2:02x})', 0)


def read_compressed_int(data, offset):
    """Read a compressed integer (CLI spec §23.2)"""
    b0 = data[offset]
    if b0 & 0x80 == 0:
        return b0, offset + 1
    elif b0 & 0xC0 == 0x80:
        val = ((b0 & 0x3F) << 8) | data[offset + 1]
        return val, offset + 2
    elif b0 & 0xE0 == 0xC0:
        val = ((b0 & 0x1F) << 24) | (data[offset+1] << 16) | (data[offset+2] << 8) | data[offset+3]
        return val, offset + 4
    else:
        raise ValueError(f"Invalid compressed int at offset {offset}: 0x{b0:02x}")


def disassemble_method(code_data, method_rva, reader, token_resolver=None):
    """
    Disassemble a CIL method body.
    code_data: raw bytes of the method body (including fat/tiny header)
    method_rva: RVA of the method (for calculating offsets)
    reader: DotNetReader for token resolution
    """
    if len(code_data) < 2:
        return ["<method body too small>"]
    
    # Determine if tiny or fat header
    flags = read_u16(code_data, 0)
    is_fat = flags & 0x0003  # bit 0 = FatFormat
    
    if not is_fat:
        # Tiny header: 1 byte, size >> 2 = code size, flags >> 2 = IL
        header_size = 1
        code_size = flags >> 2
        code_offset = 1
    else:
        # Fat header: 12 bytes
        header_size = (flags >> 12) & 0xF
        if header_size < 3:
            header_size = 3
        max_stack = read_u16(code_data, 2)
        code_size = read_u32(code_data, 4)
        local_var_sig = read_u32(code_data, 8)
        code_offset = 12
        if header_size > 3:
            code_offset = header_size * 4  # header_size is in 4-byte units for fat
    
    if code_offset >= len(code_data):
        return [f"<code offset {code_offset} >= data size {len(code_data)}>"]
    
    code = code_data[code_offset:code_offset + code_size]
    
    lines = []
    pos = 0
    while pos < len(code):
        file_offset = method_rva + code_offset + pos  # approximate
        addr = pos
        
        opcode = code[pos]
        pos += 1
        
        if opcode == 0xFE:
            # Two-byte opcode
            if pos >= len(code):
                lines.append(f"  0x{addr:04x}: FE <truncated>")
                break
            opcode2 = code[pos]
            pos += 1
            name, operand_size = get_two_byte_opcode_info(opcode2)
            full_name = f"FE {name}"
        else:
            name, operand_size = get_opcode_info(opcode)
            full_name = name
        
        # Special handling for 'switch'
        if opcode == 0x2D:  # switch
            if pos + 4 <= len(code):
                count = struct.unpack_from('<I', code, pos)[0]
                pos += 4
                targets = []
                for _ in range(count):
                    if pos + 4 <= len(code):
                        offset = struct.unpack_from('<i', code, pos)[0]
                        targets.append(f"IL_{addr + offset + 5:04x}")
                        pos += 4
                    else:
                        targets.append("???")
                target_str = ', '.join(targets)
                lines.append(f"  IL_{addr:04x}: {full_name} ({target_str})")
                continue
        
        # Read operand
        operand_str = ""
        if operand_size is not None and operand_size > 0:
            if pos + operand_size > len(code):
                lines.append(f"  IL_{addr:04x}: {full_name} <truncated operand>")
                break
            
            if operand_size == 1:
                val = code[pos]
                operand_str = f"0x{val:02x}"
                # Check if this is a branch offset
                if opcode in (0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D):
                    target = pos + operand_size + struct.unpack_from('<b', code, pos)[0]
                    operand_str = f"IL_{target:04x}"
                elif opcode == 0x15:  # ldc.i4.s
                    operand_str = f"{struct.unpack_from('<b', code, pos)[0]}"
                elif opcode in (0x06,):  # ldarg.s
                    operand_str = f"arg.{val}"
                elif opcode in (0x09,):  # ldarga.s
                    operand_str = f"arg.{val}"
                elif opcode == 0x13:  # ldloc.s  (wait, this is not ldloc.s)
                    operand_str = f"loc.{val}"
                elif opcode == 0x0E:  # this is wrong - opcode 0x0E is ldarg.2 not ldarg.s
                    pass
                pos += 1
            elif operand_size == 2:
                val = read_u16(code, pos)
                operand_str = f"0x{val:04x}"
                pos += 2
            elif operand_size == 4:
                val = read_u32(code, pos)
                # Check if this is a branch
                if opcode in (0x1C, 0x1D, 0x1E):  # jmp, call, calli
                    token = val
                    resolved = reader.resolve_token(token) if reader else f"token(0x{token:08x})"
                    operand_str = resolved
                elif opcode in (0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69):  # ldfld, ldflda, stfld, ldsfld, ldsflda, stsfld, stobj
                    token = val
                    resolved = reader.resolve_token(token) if reader else f"token(0x{token:08x})"
                    operand_str = resolved
                elif opcode == 0x5B:  # ldstr
                    resolved = reader.resolve_token(val) if reader else f"token(0x{val:08x})"
                    operand_str = resolved
                elif opcode == 0x5C:  # newobj
                    resolved = reader.resolve_token(val) if reader else f"token(0x{val:08x})"
                    operand_str = resolved
                elif opcode in (0x5D, 0x5E):  # castclass, isinst
                    resolved = reader.resolve_token(val) if reader else f"token(0x{val:08x})"
                    operand_str = resolved
                elif opcode in (0x6B, 0x8D, 0xA0, 0xE9):  # newarr
                    resolved = reader.resolve_token(val) if reader else f"token(0x{val:08x})"
                    operand_str = resolved
                elif opcode == 0x58:  # callvirt
                    resolved = reader.resolve_token(val) if reader else f"token(0x{val:08x})"
                    operand_str = resolved
                elif opcode == 0x8C:  # box
                    resolved = reader.resolve_token(val) if reader else f"token(0x{val:08x})"
                    operand_str = resolved
                elif opcode in (0x6D, 0x8F, 0xEB):  # ldelema
                    resolved = reader.resolve_token(val) if reader else f"token(0x{val:08x})"
                    operand_str = resolved
                else:
                    # Check if it looks like a metadata token (high byte 0x01-0x6E, low bytes = row)
                    if (val >> 24) in (0x01, 0x02, 0x04, 0x06, 0x08, 0x0A, 0x0C, 0x0D, 0x0E, 0x10, 0x15, 0x17, 0x1B, 0x1C, 0x1E, 0x20, 0x26, 0x27, 0x28, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F):
                        resolved = reader.resolve_token(val) if reader else f"token(0x{val:08x})"
                        operand_str = resolved
                    else:
                        operand_str = f"0x{val:08x}"
                
                # Check for branch
                if opcode in (0x1C, 0x1D, 0x1E):
                    pass  # Already resolved above
                pos += 4
            elif operand_size == 8:
                val = read_u64(code, pos)
                operand_str = f"0x{val:016x}"
                pos += 8
        
        # Also handle two-byte opcodes with 4-byte operands
        if opcode == 0xFE:
            if operand_size == 4 and pos <= len(code) - 4 + (operand_size if operand_size else 0):
                pass  # Already handled above
        
        lines.append(f"  IL_{addr:04x}: {full_name} {operand_str}")
    
    return lines


def find_method_bodies(reader, pe):
    """Find method bodies by looking for fat or tiny CIL headers at their RVAs"""
    results = []
    for i, m in enumerate(reader.method_table):
        rva = m.Rva
        if rva == 0:
            continue  # abstract/extern method
        
        offset = pe.rva_to_offset(rva)
        if offset is None:
            continue
        
        try:
            code_data = pe.data[offset:offset + 8000]  # Read generous chunk
            flags = read_u16(code_data, 0)
            is_fat = flags & 0x0003
            
            if is_fat:
                code_size = read_u32(code_data, 4)
                if code_size > 0 and code_size < 50000:
                    results.append((i + 1, rva, offset, code_size, 'fat'))
            else:
                code_size = flags >> 2
                if code_size > 0 and code_size < 50000:
                    results.append((i + 1, rva, offset, code_size, 'tiny'))
        except:
            pass
    
    return results


# ============================================================
# Main
# ============================================================
def main():
    exe_path = EXE_PATH
    if not exe_path.exists():
        print(f"ERROR: {exe_path} not found")
        sys.exit(1)
    
    print(f"[*] Loading {exe_path}...")
    reader = DotNetReader(str(exe_path))
    pe = PEFile(str(exe_path))
    
    # Find all types
    if '--list-types' in sys.argv:
        print("\n[*] All TypeDefs:")
        types = reader.list_all_types()
        for idx, name in types:
            print(f"  [{idx:4d}] {name}")
        return
    
    # Find methods by type name
    type_filter = None
    for arg in sys.argv:
        if arg.startswith('--type='):
            type_filter = arg.split('=', 1)[1]
    
    if type_filter:
        print(f"\n[*] Methods in types matching '{type_filter}':")
        methods = reader.find_methods_by_type(type_filter)
        for m in methods:
            flags_str = ""
            if m['rva'] == 0:
                flags_str = " [abstract/extern]"
            print(f"  [{m['index']:4d}] {m['type']}::{m['name']}(RVA=0x{m['rva']:x}){flags_str}")
        
        print(f"\n[*] Fields in types matching '{type_filter}':")
        fields = reader.find_fields_by_type(type_filter)
        for f in fields:
            print(f"  [{f['index']:4d}] {f['type']}::{f['name']}")
        return
    
    # Find all methods with a name
    name_filter = None
    for arg in sys.argv:
        if arg.startswith('--method='):
            name_filter = arg.split('=', 1)[1]
    
    if name_filter:
        print(f"\n[*] Methods matching '{name_filter}':")
        methods = reader.find_methods_by_name(name_filter)
        for m in methods:
            print(f"  [{m['index']:4d}] {m['type']}::{m['name']}(RVA=0x{m['rva']:x})")
        return
    
    # Disassemble specific methods
    disasm_indices = []
    for arg in sys.argv:
        if arg.startswith('--disasm='):
            disasm_indices.append(int(arg.split('=', 1)[1]))
    
    if disasm_indices:
        for idx in disasm_indices:
            m = reader.get_method_def(idx)
            if m is None:
                print(f"\n[!] MethodDef[{idx}] not found")
                continue
            
            type_name = reader.get_method_owner_type_name(idx)
            method_name = reader.get_string(m.Name)
            rva = m.Rva
            
            print(f"\n{'='*70}")
            print(f"[+] MethodDef[{idx}] {type_name}::{method_name}")
            print(f"    RVA=0x{rva:x}, Flags=0x{m.Flags:x}, ImplFlags=0x{m.ImplFlags:x}")
            
            if rva == 0:
                print("    [abstract/extern - no code body]")
                continue
            
            offset = pe.rva_to_offset(rva)
            if offset is None:
                print(f"    [RVA 0x{rva:x} not found in any section]")
                continue
            
            code_data = pe.data[offset:offset + 8000]
            
            lines = disassemble_method(code_data, rva, reader)
            for line in lines:
                print(line)
        
        return
    
    # Default: disassemble HID-related methods
    print("\n[*] Searching for HID-related methods...")
    hid_methods = reader.find_methods_by_name('hid')
    for m in hid_methods:
        print(f"  [{m['index']:4d}] {m['type']}::{m['name']}(RVA=0x{m['rva']:x})")
    
    # Disassemble key methods
    print("\n[*] Disassembling HID methods...")
    target_methods = [m['index'] for m in hid_methods if m['rva'] != 0]
    
    for idx in target_methods[:10]:  # Limit to prevent huge output
        m = reader.get_method_def(idx)
        type_name = reader.get_method_owner_type_name(idx)
        method_name = reader.get_string(m.Name)
        rva = m.Rva
        
        print(f"\n{'='*70}")
        print(f"[+] MethodDef[{idx}] {type_name}::{method_name}")
        print(f"    RVA=0x{rva:x}, Flags=0x{m.Flags:x}")
        
        if rva == 0:
            print("    [abstract/extern]")
            continue
        
        offset = pe.rva_to_offset(rva)
        if offset is None:
            print(f"    [RVA not in any section]")
            continue
        
        code_data = pe.data[offset:offset + 8000]
        lines = disassemble_method(code_data, rva, reader)
        for line in lines:
            print(line)


if __name__ == '__main__':
    main()

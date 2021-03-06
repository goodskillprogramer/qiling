#!/usr/bin/env python3
# 
# Cross Platform and Multi Architecture Advanced Binary Emulation Framework
# Built on top of Unicorn emulator (www.unicorn-engine.org)

from qiling.os.macos.define_values import *
from qiling.os.macos.mach_port import *
from qiling.const import *
from struct import *
import os


def load_shared_region(ql):
    if ql.arch == QL_X8664:
        #ql.uc.mem_write(0x7FFFFFE00010, b'\x00\x00\x00\x00')    # _COMM_PAGE_CPU_CAPABILITIES64
        ql.uc.mem_write(0x7FFFFFE00020, b'\x00\x00\x00\x00')    # _COMM_PAGE_CPU_CAPABILITIES
        ql.uc.mem_write(0x7FFFFFE0001E, b'\x0d')                # _COMM_PAGE_VERSION      
        ql.uc.mem_write(0x7FFFFFE00040, b'\xec\x5e\x3b\x57')    # _COMM_PAGE_CPUFAMILY
    elif ql.arch == QL_ARM64:
        pass

def vm_shared_region_enter(ql):
    ql.uc.mem_map(SHARED_REGION_BASE_X86_64, SHARED_REGION_SIZE_X86_64)
    ql.macos_shared_region = True
    ql.macos_shared_region_port = MachPort(9999)        # random port name
    

# I dont know what this space for
def map_somefunc_space(ql):
    if ql.arch == QL_X8664:
        addr_base = 0x7fffffe00000
        addr_size = 0x1000
    elif ql.arch == QL_ARM64:
        addr_base = 0x0000000FFFFFC000
        addr_size = 0x1000          
    ql.uc.mem_map(addr_base, addr_size)
    time_lock_slide = 0x68
    ql.uc.mem_write(addr_base+time_lock_slide, ql.pack32(0x1))


class SharedFileMappingNp:

    def __init__(self, ql):
        self.size = 32
        self.ql = ql
    
    def read_mapping(self, addr):
        content = self.ql.uc.mem_read(addr, self.size)
        self.sfm_address = unpack("<Q", self.ql.uc.mem_read(addr, 8))[0]
        self.sfm_size = unpack("<Q", self.ql.uc.mem_read(addr + 8, 8))[0]
        self.sfm_file_offset = unpack("<Q", self.ql.uc.mem_read(addr + 16, 8))[0]
        self.sfm_max_prot = unpack("<L", self.ql.uc.mem_read(addr + 24, 4))[0]
        self.sfm_init_prot = unpack("<L", self.ql.uc.mem_read(addr + 28, 4))[0]

        self.ql.nprint("[ShareFileMapping]: addr: 0x{:X}, size: 0x{:X}, fileOffset:0x{:X}, maxProt: {}, initProt: {}".format(
            self.sfm_address, self.sfm_size, self.sfm_file_offset, self.sfm_max_prot, self.sfm_init_prot
            ))


class ProcRegionWithPathInfo():

    def __init__(self, ql):
        self.ql = ql
        pass
    
    def set_path(self, path):
        self.vnode_info_path_vip_path = path

    def write_info(self, addr):
        addr += 248
        self.ql.uc.mem_write(addr, self.vnode_info_path_vip_path)


class FileSystem():

    def __init__(self, ql):
        self.ql = ql
        self.base_path = ql.rootfs

    def get_common_attr(self, path, cmn_flags):
        real_path = self.vm_to_real_path(path)
        if not os.path.exists(real_path):
            return None
        attr = b''
        file_stat = os.stat(real_path)
        filename = ""

        if cmn_flags & ATTR_CMN_NAME != 0:
            filename = path.split("/")[-1]
            filename_len = len(filename) + 1        # add \0
            attr += pack("<L", filename_len)
            self.ql.nprint("FileName :{}, len:{}".format(filename, filename_len))

        if cmn_flags & ATTR_CMN_DEVID != 0:
            attr += pack("<L", file_stat.st_dev)
            self.ql.nprint("DevID: {}".format(file_stat.st_dev))

        if cmn_flags & ATTR_CMN_OBJTYPE != 0:
            if os.path.isdir(path):
                attr += pack("<L", VDIR)
                self.ql.nprint("ObjType: DIR")
            elif os.path.islink(path):
                attr += pack("<L", VLINK)
                self.ql.nprint("ObjType: LINK")
            else:
                attr += pack("<L", VREG)
                self.ql.nprint("ObjType: REG")
            
        if cmn_flags & ATTR_CMN_OBJID != 0:
            attr += pack("<Q", file_stat.st_ino)
            self.ql.nprint("VnodeID :{}".format(file_stat.st_ino))

        # at last, add name 
        if cmn_flags & ATTR_CMN_NAME != 0:
            name_offset = len(attr) + 4
            attr = pack("<L", name_offset) + attr
            attr += filename.encode("utf8")
            attr += b'\x00'
        
        self.ql.nprint("Attr : {}".format(attr))
    
        return attr

    def vm_to_real_path(self, vm_path):
        if not vm_path:
            return None
        if vm_path[0] == '/':
            # abs path 
            return os.path.join(self.base_path, vm_path[1:])
        else:
            # rel path
            return os.path.join(self.base_path, vm_path)

    def open(self, path, open_flags, open_mode):

        real_path = self.vm_to_real_path(path)
        
        if real_path:
            return os.open(real_path, open_flags, open_mode)
        else:
            return None

    def isexists(self, path):
        real_path = self.vm_to_real_path(path)
        return os.path.exists(real_path)

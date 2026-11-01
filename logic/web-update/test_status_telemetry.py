"""Execute native telemetry helper: read-only state, ABI, guards."""
import struct,unittest
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE
from unicorn.mips_const import *
import status_telemetry as s
class TelemetryTest(unittest.TestCase):
    def test_reads_state_and_preserves_abi(self):
        for state in [0,1,2,3,0xffffffff]:
            u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
            u.mem_map(0,0x300000);u.mem_write(s.ADDRESS&0x1fffffff,s.PAYLOAD)
            u.mem_write(s.STATE&0x1fffffff,struct.pack('<I',state))
            values={UC_MIPS_REG_A0:0x123456,UC_MIPS_REG_RA:0x8000ac70,UC_MIPS_REG_SP:0x802ff000,UC_MIPS_REG_S0:0x2468}
            for reg,value in values.items():u.reg_write(reg,value)
            writes=[];u.hook_add(__import__('unicorn').UC_HOOK_MEM_WRITE,lambda *args:writes.append(args[1]))
            u.emu_start(s.ADDRESS,s.WRITER,count=12)
            self.assertEqual(u.reg_read(UC_MIPS_REG_PC),s.WRITER)
            self.assertEqual(u.reg_read(UC_MIPS_REG_A2),state)
            self.assertEqual(u.reg_read(UC_MIPS_REG_A1),0x80166aac)
            for reg,value in values.items():self.assertEqual(u.reg_read(reg),value)
            self.assertEqual(writes,[])
    def test_patch_guards(self):
        with self.assertRaises(ValueError):s.apply(bytes(2174360))
if __name__=='__main__':unittest.main()

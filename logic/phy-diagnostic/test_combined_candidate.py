"""Combined secure UI/PHY contracts, including the real Telnet builtin path."""
import unittest
from pathlib import Path
from combined_candidate import make_main, RANGES
from test_patch import Machine, reg

ROOT=Path(__file__).resolve().parent


class CombinedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=(ROOT.parent/'security/preupload-hardening/main-preupload.NOT-FLASHABLE.bin').read_bytes()
        cls.phy=(ROOT/'original-baseline/main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()

    def test_only_diagnostic_ranges_change_and_security_ui_is_preserved(self):
        result=make_main(self.base,self.phy)
        self.assertEqual(len(result),len(self.base))
        changes=[i for i,(a,b) in enumerate(zip(self.base,result)) if a!=b]
        self.assertTrue(changes)
        self.assertTrue(all(any(lo<=i<hi for lo,hi in RANGES) for i in changes))
        self.assertEqual(result[0xdf98:0xe1a0],self.base[0xdf98:0xe1a0])
        self.assertEqual(result[0xfff8:0xfffc],self.base[0xfff8:0xfffc])
        self.assertEqual(result[0x1a8d69:0x1ed000],self.base[0x1a8d69:0x1ed000])

    def test_real_telnet_builtin_query_runs_combined_payload(self):
        m=Machine(values=[0x3100,0x7869,0x786d,0x05e1,0x45e1,0x0067])
        m.u.mem_write(0x400,make_main(self.base,self.phy));m.cli(['phy'])
        m.u.reg_write(reg('s2'),2);m.u.reg_write(reg('s5'),m.u.reg_read(reg('a1'))-4)
        m.sym['builtin']=0x80112478;m.run('builtin',0x80112484)
        self.assertEqual(m.commands,[0x4000,0x4100,0x4100,0x4400,0x4500,0x4600])
        self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000)

    def test_modified_security_input_is_rejected(self):
        bad=bytearray(self.base);bad[0xe160]^=1
        with self.assertRaises(ValueError):make_main(bytes(bad),self.phy)

    def test_old_diagnostic_without_builtin_fix_is_rejected(self):
        old=(ROOT/'original-baseline/installed-v1-64421c4f/main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
        with self.assertRaises(ValueError):make_main(self.base,old)


if __name__=='__main__':unittest.main()

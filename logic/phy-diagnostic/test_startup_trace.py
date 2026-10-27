"""Execute extended trace machine code with controlled register/MMIO state."""
import struct
import unittest
import startup_trace
import hashlib
from pathlib import Path
from test_patch import Machine, reg, word, RET

class StartupTraceTests(unittest.TestCase):
    def machine(self):
        self.assertTrue(callable(getattr(startup_trace,'assemble',None)), 'startup trace encoder is missing')
        m=Machine();blob,sym=startup_trace.assemble();m.sym=sym
        m.u.mem_write(0x19f0c4,blob)
        return m

    def entry(self,m,caller=0x80003960):
        m.u.reg_write(reg('sp'),0x802f0000);m.u.reg_write(reg('ra'),caller)
        m.u.mem_write(0x2f000c,word(0x8014e1e0))
        m.u.mem_write(0x10110080,word(0x83818301))
        m.u.mem_write(0x2551d0,word(2));m.u.mem_write(0x212ca0,word(1))
        m.run('trace',0x8001713c)

    def test_records_caller_parent_link_state_and_preserves_machine(self):
        for irq in [0,1]:
            m=self.machine();m.u.reg_write(reg('cp0_status'),0x1000ff00|irq)
            saved={n:0x102000+i for i,n in enumerate(['a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7','t8','t9','s0','s1','gp','fp'])}
            for n,v in saved.items():m.u.reg_write(reg(n),v)
            self.entry(m)
            values=struct.unpack('<7I',m.u.mem_read(m.sym['records']&0x1fffffff,28))
            self.assertEqual(values,(1,0x80003960,0x8014e1e0,0x83818301,2,1,m.clock))
            self.assertEqual(m.value(m.sym['record_count']),1)
            self.assertEqual(m.u.reg_read(reg('cp0_status')),0x1000ff00|irq)
            self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000-24)
            for n,v in saved.items():self.assertEqual(m.u.reg_read(reg(n)),v,n)
            self.assertEqual(m.writes,[])

    def test_first_eight_records_freeze_while_total_counter_wraps(self):
        m=self.machine();m.u.mem_write(m.sym['counter']&0x1fffffff,word(0xfffffffe))
        for i in range(8):self.entry(m,0x8014e338)
        frozen=bytes(m.u.mem_read(m.sym['records']&0x1fffffff,224))
        for i in range(3):self.entry(m,0x80003960)
        self.assertEqual(m.value(m.sym['counter']),9)
        self.assertEqual(m.value(m.sym['record_count']),8)
        self.assertEqual(bytes(m.u.mem_read(m.sym['records']&0x1fffffff,224)),frozen)
        self.assertEqual(struct.unpack('<3I',frozen[:12]),(0xffffffff,0x8014e338,0))
        m.u.reg_write(reg('sp'),0x802f0000);m.u.reg_write(reg('ra'),RET)
        m.cli(['phy']);m.run('wrapper')
        self.assertEqual(len(m.prints),39)
        self.assertEqual([m.prints[7+4*i][1][0] for i in range(8)],list(range(8)))
        self.assertEqual(m.commands,[0x4000,0x4100,0x4100,0x4400,0x4500,0x4600])

    def test_cli_preserves_six_reads_then_outputs_trace(self):
        m=self.machine();self.entry(m)
        m.u.reg_write(reg('sp'),0x802f0000);m.u.reg_write(reg('ra'),RET)
        m.cli(['phy']);m.run('wrapper')
        self.assertEqual(m.commands,[0x4000,0x4100,0x4100,0x4400,0x4500,0x4600])
        self.assertEqual(len(m.prints),11)
        self.assertEqual(m.prints[7][1],[0,0x80003960,0x8014e1e0])
        self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000)
        self.assertEqual(m.u.reg_read(reg('ra')),RET)

    def test_legacy_arguments_still_forward(self):
        m=self.machine();m.cli(['r','b0110080']);m.run('wrapper')
        self.assertEqual(m.forward,(2,0x802e0000,0x802f0000,RET))
        self.assertEqual(m.prints,[]);self.assertEqual(m.writes,[])

    def test_candidate_changes_only_owned_payload_and_rejects_unknown_input(self):
        self.assertTrue(callable(getattr(startup_trace,'make_main',None)), 'candidate builder is missing')
        root=Path(__file__).resolve().parent
        before=(root/'combined/main-secure-ui-phy.NOT-FLASHABLE.bin').read_bytes()
        after=startup_trace.make_main(before)
        lo=0x19ecc4;hi=lo+len(startup_trace.assemble()[0])
        self.assertEqual(len(after),len(before))
        self.assertEqual(after[:lo],before[:lo]);self.assertEqual(after[hi:],before[hi:])
        self.assertNotEqual(hashlib.sha256(before).digest(),hashlib.sha256(after).digest())
        m=self.machine();m.u.mem_write(0x400,after)
        m.sym['builtin']=0x80112478;m.cli(['phy'])
        m.u.reg_write(reg('s2'),2);m.u.reg_write(reg('s5'),0x802e0000-4)
        m.run('builtin',0x80112484)
        self.assertEqual(len(m.prints),7);self.assertIsNone(m.forward)
        bad=bytearray(before);bad[100]^=1
        with self.assertRaises(ValueError):startup_trace.make_main(bytes(bad))

if __name__=='__main__':unittest.main(verbosity=2)

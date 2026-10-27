"""Execute emitted MIPS code; only physical MMIO and printf are simulated."""
import sys, struct, unittest, hashlib, lzma, zlib, json
from datetime import datetime, timezone
from pathlib import Path
# Runtime dependencies are declared in requirements.txt.
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn import mips_const as mc
import patch
import builder
RET=0x80100000
GPIO=0x10000060; PCR0=0x101100c0; PCR1=0x101100c4

def word(x): return struct.pack('<I',x & 0xffffffff)
def reg(n): return getattr(mc,'UC_MIPS_REG_'+n.upper())

class Machine:
    def __init__(self, *, busy=0, never=False, delay=0, status=0x1000ff01, mux=0x12340080, values=None):
        self.blob,self.sym=patch.assemble()
        self.u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
        for a,n in [(0,0x300000),(GPIO&~4095,4096),(PCR0&~4095,4096)]: self.u.mem_map(a,n)
        self.u.mem_write(0x19f0c4,self.blob)
        self.u.reg_write(reg('sp'),0x802f0000)
        self.u.reg_write(reg('ra'),RET)
        self.u.reg_write(reg('cp0_status'),status)
        self.values=iter(values) if values else None; self.current=0x782d; self.clock=0x12345678
        self.status=status; self.mux=mux; self.writes=[]; self.polls=0; self.commands=[]; self.prints=[]; self.forward=None
        self.u.mem_write(GPIO,word(mux)); self.u.mem_write(PCR0,word(busy))
        def read(u,access,addr,size,value,data):
            p=addr&0x1fffffff
            if p in [GPIO,PCR0,PCR1]: assert not u.reg_read(reg('cp0_status'))&1
            if p==PCR1:
                self.polls+=1
                done=not never and self.polls>delay
                u.mem_write(PCR1,word((self.current<<16)|(2 if done else 0)))
                if done:u.mem_write(PCR0,word(0))
        def write(u,access,addr,size,value,data):
            p=addr&0x1fffffff
            if p in [GPIO,PCR0,PCR1]:
                assert not u.reg_read(reg('cp0_status'))&1
                assert p in [GPIO,PCR0]
                self.writes.append((p,value))
                if p==PCR0:
                    assert value&0x6000==0x4000, 'PHY configuration write!'
                    self.commands.append(value)
                    if self.values:self.current=next(self.values)
        def code(u,addr,size,data):
            if addr==self.sym['read_count']:
                u.reg_write(reg('t3'),self.clock);u.reg_write(reg('pc'),addr+4)
            elif addr==0x8014fca8:
                assert u.reg_read(reg('cp0_status'))==status, 'printf with altered interrupts'
                args=[u.reg_read(reg(n)) for n in ['a0','a1','a2','a3']]
                fmt=bytes(u.mem_read(args[0]&0x1fffffff,128)).split(b'\0')[0].decode()
                self.prints.append((fmt,args[1:]))
                # Model caller-clobbered registers to catch reliance on printf internals.
                for n in ['v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7','t8','t9']: u.reg_write(reg(n),0xdeadbeef)
                u.reg_write(reg('pc'),u.reg_read(reg('ra')))
            elif addr==0x80112960:
                self.forward=(u.reg_read(reg('a0')),u.reg_read(reg('a1')),u.reg_read(reg('sp')),u.reg_read(reg('ra')))
                u.reg_write(reg('v0'),0x12345678);u.reg_write(reg('pc'),RET)
        self.u.hook_add(UC_HOOK_MEM_READ,read);self.u.hook_add(UC_HOOK_MEM_WRITE,write);self.u.hook_add(UC_HOOK_CODE,code)
    def run(self,name,stop=RET):
        self.u.emu_start(self.sym[name],stop,timeout=5000000,count=1200000)
        assert self.u.reg_read(reg('pc'))==stop, 'did not return within bound'
    def value(self,address): return struct.unpack('<I',self.u.mem_read(address&0x1fffffff,4))[0]
    def cli(self,argv):
        self.u.reg_write(reg('a0'),len(argv));self.u.reg_write(reg('a1'),0x802e0000)
        for i,s in enumerate(argv):
            p=0x802e0100+i*128;self.u.mem_write(p&0x1fffffff,s.encode()+b'\0');self.u.mem_write(0x2e0000+i*4,word(p))

class ReaderTests(unittest.TestCase):
    def test_success_preserves_machine_state_and_never_writes_phy(self):
        for status,mux,delay,phy,r in [(0x1000ff01,0x12340080,0,0,1),(0x1000ff00,0x12340000,20,4,6)]:
            with self.subTest(status=status):
                m=Machine(status=status,mux=mux,delay=delay);m.u.reg_write(reg('a0'),phy);m.u.reg_write(reg('a1'),r);m.run('reader')
                self.assertEqual(m.u.reg_read(reg('v0')),0x782d);self.assertEqual(m.commands,[0x4000|r<<8|phy]);self.assertEqual(m.u.reg_read(reg('cp0_status')),status);self.assertEqual(m.value(GPIO),mux)
    def test_busy_and_invalid_requests_have_no_hardware_writes(self):
        for busy,phy,r,want in [(0x4000,0,1,-2),(0x2000,0,1,-2),(0,5,1,-1),(0,0,7,-1),(0,0xffffffff,0,-1)]:
            with self.subTest(busy=busy,phy=phy,r=r):
                m=Machine(busy=busy);m.u.reg_write(reg('a0'),phy);m.u.reg_write(reg('a1'),r);m.run('reader');self.assertEqual(m.u.reg_read(reg('v0')),want&0xffffffff);self.assertEqual(m.writes,[]);self.assertEqual(m.u.reg_read(reg('cp0_status')),m.status)
    def test_timeout_is_bounded_and_restores_interrupts_and_pinmux(self):
        m=Machine(never=True);m.u.reg_write(reg('a1'),1);m.run('reader');self.assertEqual(m.polls,65536);self.assertEqual(m.u.reg_read(reg('v0')),0xfffffffd);self.assertEqual(m.value(GPIO),m.mux);self.assertEqual(m.u.reg_read(reg('cp0_status')),m.status)

class IntegrationTests(unittest.TestCase):
    def test_phy_command_reads_bmsr_twice_and_preserves_abi(self):
        m=Machine(values=[0x3300,0x7809,0x782d,0x5e1,0xc5e1,1]);m.cli(['phy']);saved={n:0xa000+i for i,n in enumerate(['s0','s1','s2','s3','s4','s5','s6','s7','fp','gp'])}
        for n,v in saved.items():m.u.reg_write(reg(n),v)
        m.run('wrapper');self.assertIsNone(m.forward);self.assertEqual(m.commands,[0x4000,0x4100,0x4100,0x4400,0x4500,0x4600]);self.assertEqual(len(m.prints),7)
        self.assertEqual([args[0] for fmt,args in m.prints[1:]],[0,1,1,4,5,6]);self.assertEqual([args[1] for fmt,args in m.prints[1:]],[0x3300,0x7809,0x782d,0x5e1,0xc5e1,1]);self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000)
        for n,v in saved.items():self.assertEqual(m.u.reg_read(reg(n)),v,n)
    def test_other_cli_arguments_forward_untouched(self):
        for argv in [[],['r','b0110080'],['w','b01100c0','0'],['phyx'],['phy','0'],['p'],['ph']]:
            with self.subTest(argv=argv):
                m=Machine();m.cli(argv);m.run('wrapper');self.assertEqual(m.forward,(len(argv),0x802e0000,0x802f0000,RET));self.assertEqual(m.prints,[]);self.assertEqual(m.writes,[])
    def test_failed_phy_read_stops_further_transactions(self):
        for kwargs,want in [({'busy':0x4000},0xfffffffe),({'never':True},0xfffffffd)]:
            m=Machine(**kwargs);m.cli(['phy']);m.run('wrapper');self.assertEqual(len(m.prints),2);self.assertEqual(m.prints[1][1][1],want);self.assertLessEqual(len(m.commands),1)
    def test_relink_trace_preserves_entry_and_counts_calls(self):
        for status in [0x1000ff00,0x1000ff01]:
            m=Machine(status=status)
            saved={n:0xa100+i for i,n in enumerate(['a0','a1','a2','a3','t0','t1','t2','t3','s0','s1','ra','gp'])}
            for n,v in saved.items():m.u.reg_write(reg(n),v)
            for count in [1,2]:
                m.run('trace',0x8001713c);self.assertEqual(m.value(m.sym['counter']),count);self.assertEqual(m.value(m.sym['counter']+4),0x12345678);self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000-24);self.assertEqual(m.u.reg_read(reg('v0')),0x80170000);self.assertEqual(m.u.reg_read(reg('cp0_status')),status)
                for n,v in saved.items():self.assertEqual(m.u.reg_read(reg(n)),v,n)
                m.u.reg_write(reg('sp'),0x802f0000)
            self.assertEqual(m.writes,[])
            m.u.reg_write(reg('ra'),RET);m.cli(['phy']);m.run('wrapper');self.assertEqual(m.prints[0][1][:2],[2,0x12345678])

class ImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parent.parent
        cls.main=(root/'web-update/main-web-update.NOT-FLASHABLE.bin').read_bytes()
        cls.source=(root/'uimage.bin').read_bytes()
    def test_only_three_reviewed_ranges_change_and_input_is_untouched(self):
        before=hashlib.sha256(self.main).hexdigest()
        result=builder.patch_main(self.main)
        self.assertEqual(len(result),2174360)
        self.assertEqual(hashlib.sha256(self.main).hexdigest(),before)
        allowed=[(0x19ecc4,0x19ecc4+len(patch.assemble()[0])),(0x16d34,0x16d3c),(0x211ff0,0x211ff4)]
        changes=[i for i,(a,b) in enumerate(zip(self.main,result)) if a!=b]
        self.assertTrue(changes)
        self.assertTrue(all(any(lo<=i<hi for lo,hi in allowed) for i in changes))
        m=Machine();m.u.mem_write(0x400,result);m.run('trace',0x8001713c)
        self.assertEqual(m.value(m.sym['counter']),1)
        self.assertEqual(struct.unpack_from('<I',result,0x211ff0)[0],m.sym['wrapper'])
        # Execute the actual patched entry, including its jump/delay slot.
        m.u.reg_write(reg('sp'),0x802f0000);m.sym['entry']=0x80017134;m.run('entry',0x8001713c)
        self.assertEqual(m.value(m.sym['counter']),2)
    def test_rejects_changed_source_instead_of_patching_unknown_firmware(self):
        bad=bytearray(self.main);bad[1]^=1
        with self.assertRaises(ValueError):builder.patch_main(bytes(bad))
        bad=bytearray(self.source);bad[-1]^=1
        with self.assertRaises(ValueError):builder.package(bytes(bad),self.main)
    def test_packaging_roundtrips_and_preserves_size_loader_and_valid_crcs(self):
        main=builder.patch_main(self.main);image,compressed_size=builder.package(self.source,main)
        self.assertEqual(len(image),718108);self.assertLessEqual(compressed_size,708764)
        self.assertEqual(image[64:64+0x2440],self.source[64:64+0x2440])
        self.assertEqual(lzma.decompress(image[64+0x2440:64+0x2440+compressed_size],format=lzma.FORMAT_ALONE),main)
        self.assertEqual(zlib.crc32(image[64:]),struct.unpack_from('>I',image,24)[0])
        header=bytearray(image[:64]);wanted=struct.unpack_from('>I',header,4)[0];header[4:8]=bytes(4)
        self.assertEqual(zlib.crc32(header),wanted)
        self.assertEqual(image[64+0x2440+compressed_size:],b'\xff'*(708764-compressed_size))

if __name__=='__main__':
    result=unittest.main(verbosity=2,exit=False).result
    root=Path(__file__).resolve().parent
    report={'status':'PASS' if result.wasSuccessful() else 'FAIL','utc':datetime.now(timezone.utc).isoformat(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'test_scope':'Actual MIPS machine code with simulated MMIO, printf, CP0 Count sample; not a real device.','payload_sha256':hashlib.sha256(patch.assemble()[0]).hexdigest()}
    (root/'test-results.json').write_text(json.dumps(report,indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)

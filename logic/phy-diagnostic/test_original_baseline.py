"""Original-baseline image contracts; full emitted MIPS code uses simulated MMIO."""
import hashlib,lzma,struct,unittest,zlib
from pathlib import Path
import builder
from test_patch import Machine,reg,RET
from unicorn import UC_HOOK_CODE
ROOT=Path(__file__).resolve().parent

class OriginalBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=(ROOT.parent/'main-decompressed.bin').read_bytes()
        cls.source=(ROOT.parent/'uimage.bin').read_bytes()
    def patched(self):
        try:return builder.patch_main(self.original)
        except ValueError as e:self.fail('Known original baseline must be supported: '+str(e))
    def test_telnet_builtin_reg_dispatch_reaches_diagnostic_and_returns(self):
        main=self.patched();m=Machine(values=[0x3300,0x7809,0x782d,0x5e1,0xc5e1,1])
        m.u.mem_write(0x400,main);m.cli(['phy'])
        argv=m.u.reg_read(reg('a1'))
        m.u.reg_write(reg('s2'),2);m.u.reg_write(reg('s5'),argv-4)
        m.sym['telnet_dispatch']=0x80112478
        m.run('telnet_dispatch',0x80112484)
        self.assertEqual(m.commands,[0x4000,0x4100,0x4100,0x4400,0x4500,0x4600])
        self.assertIsNone(getattr(m,'forward',None))
        self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000)
    def test_original_pages_defaults_and_all_other_bytes_remain_unchanged(self):
        original_hash=hashlib.sha256(self.original).hexdigest();main=self.patched()
        self.assertEqual(len(main),2174360)
        self.assertEqual(hashlib.sha256(self.original).hexdigest(),original_hash)
        allowed=[(0xa4b0,0xa4b4),(0x16d34,0x16d3c),(0x11207c,0x112080),(0x19ecc2,0x19f140),(0x211ff0,0x211ff4)]
        changed=[i for i,(a,b) in enumerate(zip(self.original,main)) if a!=b]
        self.assertTrue(changed)
        self.assertTrue(all(any(a<=i<b for a,b in allowed) for i in changed))
        self.assertEqual(main[0x19e1a5],ord('7'))
        # The original index, login and script allocations must retain every byte.
        for a,b in [(0x1a8d69,0x1ab6a1),(0x1ad83c,0x1c4e66),(0x1d4a20,0x1d6d63)]:
            self.assertEqual(main[a:b],self.original[a:b])
    def test_package_keeps_container_loader_crcs_and_full_main_roundtrip(self):
        main=self.patched();image,size=builder.package(self.source,main,nice_len=64)
        self.assertEqual(len(image),718108);self.assertLessEqual(size,708764)
        self.assertEqual(image[64:64+0x2440],self.source[64:64+0x2440])
        self.assertEqual(image[64+0x2440:64+0x2445],self.source[64+0x2440:64+0x2445])
        self.assertEqual(lzma.decompress(image[64+0x2440:],format=lzma.FORMAT_ALONE),main)
        self.assertEqual(image[64+0x2440+size:],b'\xff'*(708764-size))
        h=bytearray(image[:64]);crc=struct.unpack_from('>I',h,4)[0];h[4:8]=bytes(4)
        self.assertEqual(zlib.crc32(h),crc)
        self.assertEqual(zlib.crc32(image[64:]),struct.unpack_from('>I',h,24)[0])
    def test_oversized_real_compression_profile_is_rejected(self):
        main=self.patched()
        with self.assertRaisesRegex(ValueError,'budget'):
            builder.package(self.source,main,nice_len=273)
    def test_unknown_original_and_container_are_rejected(self):
        self.patched()
        bad=bytearray(self.original);bad[0]^=1
        with self.assertRaises(ValueError):builder.patch_main(bytes(bad))
        bad=bytearray(self.source);bad[-1]^=1
        with self.assertRaises(ValueError):builder.package(bytes(bad),self.original,nice_len=64)
    def test_full_image_entry_and_phy_command_execute_and_preserve_state(self):
        main=self.patched();m=Machine(values=[0x3300,0x7809,0x782d,0x5e1,0xc5e1,1]);m.u.mem_write(0x400,main)
        m.sym['entry']=0x80017134;m.run('entry',0x8001713c)
        self.assertEqual(m.value(m.sym['counter']),1)
        self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000-24)
        m.u.reg_write(reg('sp'),0x802f0000);m.u.reg_write(reg('ra'),RET);m.cli(['phy'])
        callback=struct.unpack_from('<I',main,0x211ff0)[0];m.sym['callback']=callback;m.run('callback')
        self.assertEqual(m.commands,[0x4000,0x4100,0x4100,0x4400,0x4500,0x4600])
        self.assertEqual([args[1] for fmt,args in m.prints[1:]],[0x3300,0x7809,0x782d,0x5e1,0xc5e1,1])
        self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000)
    def test_favicon_callback_returns_no_instruction_bytes(self):
        main=self.patched();m=Machine();m.u.mem_write(0x400,main);calls=[]
        m.u.reg_write(reg('a0'),0x1234);m.u.reg_write(reg('a1'),0x8019f0c2)
        def raw_write(u,address,size,unused):
            if address==0x80011ef0:
                calls.append(tuple(u.reg_read(reg(n)) for n in ['a0','a1','a2','a3']))
                u.reg_write(reg('pc'),u.reg_read(reg('ra')))
        m.u.hook_add(UC_HOOK_CODE,raw_write);m.sym['favicon']=0x8000a8a8;m.run('favicon')
        self.assertEqual(calls,[(0x1234,0x8019f0c2,0,0)])
        self.assertEqual(m.u.reg_read(reg('sp')),0x802f0000)

class IndependentOriginalVerifierTests(unittest.TestCase):
    def fixtures(self):
        import json
        d=ROOT/'original-baseline'
        return [(ROOT.parent/'uimage.bin').read_bytes(),(ROOT.parent/'main-decompressed.bin').read_bytes(),
                (d/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes(),
                (d/'phy-diagnostic.uimage.NOT-FOR-FLASHING.bin').read_bytes(),
                (d/'payload.bin').read_bytes(),json.loads((d/'build-manifest.json').read_text())]
    def inspect(self,values):
        try:import verify_original
        except ModuleNotFoundError:self.fail('Independent original-baseline verifier is not implemented')
        return verify_original.inspect_artifacts(*values)
    def test_accepts_written_original_based_artifacts(self):
        result=self.inspect(self.fixtures())
        self.assertEqual(result['changed_main_bytes'],1067)
        self.assertEqual(result['headroom_bytes'],156)
        self.assertFalse(result['hardware_validated'])
    def test_rejects_corrupt_compressed_payload(self):
        values=self.fixtures();bad=bytearray(values[3]);bad[64+0x2440+100]^=1;values[3]=bytes(bad)
        with self.assertRaises(ValueError):self.inspect(values)
    def test_rejects_forged_manifest_and_valid_crcs_for_changed_default(self):
        values=self.fixtures();main=bytearray(values[2]);main[0x19e1a5]=ord('0');values[2]=bytes(main)
        c=lzma.compress(values[2],format=lzma.FORMAT_ALONE,filters=[dict(id=lzma.FILTER_LZMA1,dict_size=8*1024*1024,lc=3,lp=0,pb=2,mode=lzma.MODE_NORMAL,nice_len=64,mf=lzma.MF_BT4)])
        c=c[:5]+struct.pack('<Q',len(main))+c[13:];self.assertLessEqual(len(c),708764)
        payload=values[0][64:64+0x2440]+c+b'\xff'*(708764-len(c));h=bytearray(values[0][:64])
        struct.pack_into('>I',h,24,zlib.crc32(payload));h[4:8]=bytes(4);struct.pack_into('>I',h,4,zlib.crc32(h))
        values[3]=bytes(h)+payload;values[5]['main_sha256']=hashlib.sha256(values[2]).hexdigest()
        values[5]['uimage_sha256']=hashlib.sha256(values[3]).hexdigest();values[5]['compressed_bytes']=len(c)
        values[5]['headroom_bytes']=708764-len(c)
        with self.assertRaises(ValueError):self.inspect(values)
    def test_rejects_truncated_container(self):
        values=self.fixtures();values[3]=values[3][:-1]
        with self.assertRaises(ValueError):self.inspect(values)

class SelectedBaselineGuardTests(unittest.TestCase):
    def test_build_rejects_other_known_baseline_before_creating_output(self):
        import tempfile
        source=(ROOT.parent/'uimage.bin').read_bytes()
        original=(ROOT.parent/'main-decompressed.bin').read_bytes()
        ui=(ROOT.parent/'web-update/main-web-update.NOT-FLASHABLE.bin').read_bytes()
        for selected,wrong,path in [('original',ui,'main-decompressed.bin'),('ui',original,'web-update/main-web-update.NOT-FLASHABLE.bin')]:
            with self.subTest(selected=selected),tempfile.TemporaryDirectory() as tmp:
                temp_root=Path(tmp)/'analysis'/'phy-diagnostic';temp_root.mkdir(parents=True)
                input_path=temp_root.parent/path;input_path.parent.mkdir(parents=True,exist_ok=True);input_path.write_bytes(wrong)
                (temp_root.parent/'uimage.bin').write_bytes(source)
                old_root=builder.ROOT;builder.ROOT=temp_root
                try:
                    with self.assertRaisesRegex(ValueError,'baseline'):builder.build(selected)
                    self.assertFalse((temp_root/builder.IMAGE_NAME).exists())
                    self.assertFalse((temp_root/'original-baseline').exists())
                finally:builder.ROOT=old_root

if __name__=='__main__':unittest.main(verbosity=2)

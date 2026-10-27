"""Exercise the capture pipeline with a simulated physical reader; no sockets/AP."""
import contextlib,hashlib,io,json,struct,tempfile,unittest,stat
from pathlib import Path
from unittest.mock import patch
import full_backup as capture
from flash_backup import ReadTimeout
from verify_full import inspect_copies

class PipelineTests(unittest.TestCase):
    def test_existing_destination_is_private_before_connection(self):
        observed=[]
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'capture';dest.mkdir(mode=0o755);dest.chmod(0o755)
            class Reader:
                def __enter__(self):observed.append(stat.S_IMODE(dest.stat().st_mode));raise TimeoutError('stop before reading')
                def __exit__(self,*args):pass
            with patch.object(capture,'DEST',dest),patch.object(capture,'Session',Reader),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(TimeoutError):capture.main()
            self.assertEqual(observed,[0o700,0o700])

    def test_two_full_copies_repair_corrupt_rows_and_resume_without_network(self):
        old=(Path(__file__).resolve().parent.parent/'flash.bin').read_bytes()
        fixture=old+b'\xff'*(2097152-len(old));opened=[];closed=[];small=[];fail_once=[True];wrong_once=[True]
        class Reader:
            def __enter__(self):opened.append(1);return self
            def __exit__(self,*args):closed.append(1)
            def read(self,address,count):
                if fail_once[0]:fail_once[0]=False;raise ReadTimeout(b'local partial')
                if address<0 or address+count>2097152:raise AssertionError('Out-of-range physical read')
                words=struct.unpack('<'+'I'*(count//4),fixture[address:address+count])
                rows=[' '.join(f'{v:08x}' for v in words[i:i+4]) for i in range(0,len(words),4)]
                if address==0 and count==1024:
                    if wrong_once[0]:
                        rows[0]='deadbeef'+rows[0][8:];wrong_once[0]=False
                    else:rows[0]='1'+rows[0] # unknown9-digit word must be re-read
                if count==16:small.append(address)
                return ('\n'.join(rows)+'\nOS>').encode()
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'capture'
            with patch.object(capture,'DEST',dest),patch.object(capture,'Session',Reader),contextlib.redirect_stdout(io.StringIO()):
                capture.main()
                first=(dest/'flash-2m-copy0.bin').read_bytes();second=(dest/'flash-2m-copy1.bin').read_bytes()
                self.assertEqual(first,fixture);self.assertEqual(second,fixture)
                self.assertEqual(small,[0,0,0,0,0,0]);self.assertEqual(opened,[1,1]);self.assertEqual(closed,[1,1])
                self.assertTrue(inspect_copies(first,second)['payload_crc_valid'])
                failures=list(dest.glob('*-timeout-*.raw'));self.assertEqual(len(failures),1);self.assertEqual(failures[0].read_bytes(),b'local partial')
                capture.main() # all verified blocks exist: skip physical reader
                self.assertEqual(opened,[1,1]);self.assertEqual(closed,[1,1])
                manifest=json.loads((dest/'manifest.json').read_text());self.assertEqual(manifest['status'],'PASS');self.assertTrue(manifest['all_connections_closed']);self.assertEqual(len(manifest['block_disagreements']),1)
                # A damaged saved block must be rejected before any new device access.
                saved=dest/'000000-copy0.bin';bad=bytearray(saved.read_bytes());bad[0]^=1;saved.write_bytes(bad)
                with self.assertRaisesRegex(ValueError,'Saved verified block hash mismatch'):capture.main()
                self.assertEqual(opened,[1,1]);self.assertEqual(json.loads((dest/'manifest.json').read_text())['status'],'INCOMPLETE')
    def test_read_failure_closes_connection_and_never_reports_full_backup(self):
        opened=[];closed=[]
        class FailingReader:
            def __enter__(self):opened.append(1);return self
            def __exit__(self,*args):closed.append(1)
            def read(self,address,count):raise TimeoutError('simulated transport failure')
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'capture'
            with patch.object(capture,'DEST',dest),patch.object(capture,'Session',FailingReader),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(TimeoutError):capture.main()
            manifest=json.loads((dest/'manifest.json').read_text());self.assertEqual(manifest['status'],'INCOMPLETE');self.assertTrue(manifest['all_connections_closed']);self.assertEqual(opened,[1,1]);self.assertEqual(closed,[1,1]);self.assertFalse((dest/'flash-2m-copy0.bin').exists())
    def test_persistent_disagreement_rejects_both_pairs_and_stops(self):
        starts=[];closed=[]
        class Reader:
            def __enter__(self):return self
            def __exit__(self,*args):closed.append(1)
            def read(self,address,count):
                words=['00000000']*(count//4)
                if address==0:
                    starts.append(1)
                    if len(starts)%2:words[0]='deadbeef'
                return ('\n'.join(' '.join(words[i:i+4]) for i in range(0,len(words),4))+'\nOS>').encode()
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'capture'
            with patch.object(capture,'DEST',dest),patch.object(capture,'Session',Reader),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'after two full pairs'):capture.main()
            m=json.loads((dest/'manifest.json').read_text());self.assertEqual(m['status'],'INCOMPLETE');self.assertEqual(len(m['block_disagreements']),2);self.assertEqual(len(starts),4);self.assertEqual(closed,[1]);self.assertFalse((dest/'000000-copy0.bin').exists())
if __name__=='__main__':unittest.main(verbosity=2)

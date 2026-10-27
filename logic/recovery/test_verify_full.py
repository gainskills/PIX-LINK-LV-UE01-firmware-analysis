"""Independent backup-integrity checks with a real known uImage fixture."""
import unittest
from pathlib import Path
from verify_full import inspect_copies
class BackupVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old=(Path(__file__).resolve().parent.parent/'flash.bin').read_bytes()
        cls.fixture=old+b'\xff'*(0x200000-len(old))
    def test_matching_full_copies_with_valid_uimage(self):
        result=inspect_copies(self.fixture,self.fixture)
        self.assertEqual(result['bytes'],2097152)
        self.assertEqual(result['uimage_bytes'],718108)
        self.assertTrue(result['upper_mib_all_ff'])
        self.assertFalse(result['jedec_id_verified'])
    def test_rejects_short_or_differing_copies(self):
        with self.assertRaises(ValueError):inspect_copies(self.fixture[:-1],self.fixture[:-1])
        changed=bytearray(self.fixture);changed[0x190000]^=1
        with self.assertRaises(ValueError):inspect_copies(self.fixture,bytes(changed))
    def test_rejects_agreeing_copies_with_corrupt_firmware(self):
        changed=bytearray(self.fixture);changed[0x60000]^=1
        with self.assertRaises(ValueError):inspect_copies(bytes(changed),bytes(changed))
    def test_rejects_header_corruption_even_when_both_copies_agree(self):
        changed=bytearray(self.fixture);changed[0x50004]^=1
        with self.assertRaises(ValueError):inspect_copies(bytes(changed),bytes(changed))
if __name__=='__main__':unittest.main(verbosity=2)

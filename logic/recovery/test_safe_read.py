import unittest
from safe_read import collect_rows
class SegmentTests(unittest.TestCase):
    def test_contaminated_chunk_is_re_read_in_smaller_segments(self):
        calls=[]
        def reader(address,count,label):
            calls.append((address,count))
            if count>16:return b'00000000 00000000 00000000 00000000\n185, flush one!\nOS>'
            return b'11223344 55667788 99aabbcc ddeeff00\nOS>'
        rows=collect_rows(reader,0x40000,32,'test',chunk=32)
        self.assertEqual(rows,[bytes.fromhex('4433221188776655ccbbaa9900ffeedd')]*2)
        self.assertEqual(calls,[(0x40000,32),(0x40000,32),(0x40000,16),(0x40010,16)])
    def test_unmappable_small_response_is_never_guessed(self):
        calls=[]
        def reader(address,count,label):calls.append((address,count));return b'noise\nOS>'
        with self.assertRaises(ValueError):collect_rows(reader,0,16,'test')
        self.assertEqual(calls,[(0,16),(0,16)])
    def test_unknown_corrupt_words_remain_missing_for_separate_double_reads(self):
        def reader(address,count,label):return b'111223344 55667788 99aabbcc ddeeff00\nOS>'
        self.assertEqual(collect_rows(reader,0,16,'test'),[None])
if __name__=='__main__':unittest.main(verbosity=2)

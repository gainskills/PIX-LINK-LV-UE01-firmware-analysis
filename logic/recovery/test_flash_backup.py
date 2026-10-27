import struct,unittest
from flash_backup import parse_read, partial_read, read_command, prompt_frame
class ParserTests(unittest.TestCase):
    def test_prompt_followed_by_async_log_completes_without_hiding_preceding_logs(self):
        self.assertEqual(prompt_frame(b'11223344 55667788 99aabbcc ddeeff00\nOS>185, flush one!\n'),b'11223344 55667788 99aabbcc ddeeff00\nOS>')
        self.assertEqual(prompt_frame(b'185, flush one!\nOS>'),b'185, flush one!\nOS>')
        with self.assertRaises(ValueError):prompt_frame(b'not complete')
    def test_never_wraps_address_or_exceeds_photographed_flash_window(self):
        self.assertEqual(read_command(0x1ffff0,16),'spi rd 1ffff0 16')
        for address,count in [(0x200000,16),(0x1ffff0,32),(-16,16),(1,16),(0,0),(0,16385),(0,32768)]:
            with self.subTest(address=address,count=count):
                with self.assertRaises(ValueError):read_command(address,count)
    def test_four_words_per_line_little_endian(self):
        self.assertEqual(parse_read(b'spi rd 100000 16\r\n12345678 00000000 ffffffff abcdef01 \r\n\r\nOS>',16),bytes.fromhex('7856341200000000ffffffff01efcdab'))
    def test_rejects_corruption_truncation_and_extra_output(self):
        for raw in [b'123456789 00000000 ffffffff abcdef01\nOS>',b'12345678 00000000\nOS>',b'12345678 00000000 ffffffff abcdef01\n',b'SPI: flash read err!!\n12345678 00000000 ffffffff abcdef01\nOS>',b'12345678 00000000 ffffffff abcdef01\nunexpected message\nOS>',b'12345678 00000000 ffffffff abcdef01\n11111111\nOS>']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):parse_read(raw,16)
    def test_no_silent_acceptance_of_wrong_echo(self):
        with self.assertRaises(ValueError):parse_read(b'spi wr 0 ff\n12345678 00000000 ffffffff abcdef01\nOS>',16)
    def test_partial_reader_never_truncates_corrupt_words(self):
        pieces=partial_read(b'12345678 00000000 ffffffff abcdef01\n123456789 00000000 ffffffff abcdef01\nOS>',32)
        self.assertEqual(pieces,[bytes.fromhex('7856341200000000ffffffff01efcdab'),None])
    def test_extra_hex_character_is_re_read_instead_of_used(self):
        self.assertEqual(partial_read(b'12345678 00000000 ffffffff abcdef01 f\nOS>',16),[None])
    def test_partial_reader_rejects_missing_or_inserted_rows(self):
        with self.assertRaises(ValueError):partial_read(b'12345678 00000000 ffffffff abcdef01\nOS>',32)
        with self.assertRaises(ValueError):partial_read(b'12345678 00000000 ffffffff abcdef01\nnoise\nOS>',16)
if __name__=='__main__':unittest.main(verbosity=2)

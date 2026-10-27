"""Validate fault evidence parsing without AP access."""
import unittest
from capture_phy_fault import parse_phy


def response(values=(0x3100,0x7869,0x786d,0x05e1,0x45e1,0x0067), calls=2):
    lines=[f'PHYDIAG relink_calls={calls} last_cp0_count=253401']
    for reg,value in zip([0,1,1,4,5,6],values):
        lines.append(f'PHYDIAG p0 reg={reg} result={value} hex={value & 0xffffffff:04x}')
    return ('\r\n'.join(lines)+'\r\nOS>').encode()


class PhyEvidenceTests(unittest.TestCase):
    def test_startup_trace_attempt_requires_its_own_verified_result(self):
        import tempfile,json
        from pathlib import Path
        from capture_phy_fault import installation_paths
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'combined-install-attempt.json').write_text('{}')
            (p/'combined-install-result.json').write_text(json.dumps(dict(candidate_sha256='c2948bec9931d02837ccfe09b5f53aaf55b4e4cd00c1e6060c310f48a68b175a',phy_six_reads_valid=True)))
            (p/'startup-trace-install-attempt.json').write_text('{}')
            with self.assertRaises(FileNotFoundError):installation_paths(p)
            path=p/'startup-trace-install-result.json'
            record=dict(candidate_sha256='81db3776965f1bf10c76549cc9ffb942cfbd481c439cf4c1cf10a72b2f9de377',phy_six_reads_valid=True,startup_trace_valid=False)
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):installation_paths(p)
            record['startup_trace_valid']=True;path.write_text(json.dumps(record))
            self.assertEqual(installation_paths(p)[0].name,'startup-trace-install-attempt.json')

    def test_combined_installation_never_falls_back_to_stale_baseline(self):
        import tempfile,json
        from pathlib import Path
        from capture_phy_fault import installation_paths
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'phy-builtin-v2-install-attempt.json').write_text('{}')
            (p/'phy-builtin-v2-install-result.json').write_text(json.dumps(dict(candidate_sha256='ae98632494f7df945e99ad534a905b009c388ed326991e50a2a8d2beab40481e',phy_six_reads_valid=True)))
            self.assertEqual(installation_paths(p)[0].name,'phy-builtin-v2-install-attempt.json')
            (p/'combined-install-attempt.json').write_text('{}')
            with self.assertRaises(FileNotFoundError):installation_paths(p)
            (p/'combined-install-result.json').write_text(json.dumps(dict(candidate_sha256='wrong',phy_six_reads_valid=True)))
            with self.assertRaises(ValueError):installation_paths(p)
            (p/'combined-install-result.json').write_text(json.dumps(dict(candidate_sha256='c2948bec9931d02837ccfe09b5f53aaf55b4e4cd00c1e6060c310f48a68b175a',phy_six_reads_valid=True)))
            self.assertEqual(installation_paths(p)[0].name,'combined-install-attempt.json')

    def test_preserves_both_bmsr_values_and_current_link(self):
        p=parse_phy(response())
        self.assertTrue(p['complete_valid'])
        self.assertEqual([r['result'] for r in p['rows'] if r['reg']==1],[0x7869,0x786d])
        self.assertEqual(p['bmsr_link'],[False,True])
        self.assertEqual(p['relink_calls'],2)

    def test_zero_readings_are_valid_evidence(self):
        p=parse_phy(response([0]*6,calls=0))
        self.assertTrue(p['complete_valid']);self.assertEqual(p['bmsr_link'],[False,False])

    def test_partial_error_is_preserved_without_invented_values(self):
        p=parse_phy(response([0x3100,0x7869,-2]))
        self.assertFalse(p['complete_valid'])
        self.assertEqual(len(p['rows']),3)
        self.assertEqual(p['rows'][-1]['result'],-2)
        self.assertEqual(p['rows'][-1]['hex'],'fffffffe')
        self.assertNotIn('bmsr_link',p)

    def test_rejects_mismatched_hex(self):
        p=parse_phy(response().replace(b'result=12544 hex=3100',b'result=12544 hex=3101'))
        self.assertFalse(p['complete_valid']);self.assertTrue(p['errors'])

    def test_rejects_truncation_and_duplicate_summary(self):
        for raw in [response()[:-30],response()+b'\nPHYDIAG relink_calls=2 last_cp0_count=3\n']:
            with self.subTest(raw=raw):self.assertFalse(parse_phy(raw)['complete_valid'])

    def test_rejects_out_of_order_and_malformed_lines(self):
        for raw in [response().replace(b'p0 reg=4',b'p0 reg=5'),response().replace(b'hex=3100',b'hex=31LOG00')]:
            with self.subTest(raw=raw):self.assertFalse(parse_phy(raw)['complete_valid'])

    def test_counter_boundary_accepted_overflow_rejected(self):
        self.assertTrue(parse_phy(response(calls=0xffffffff))['complete_valid'])
        self.assertFalse(parse_phy(response(calls=0x100000000))['complete_valid'])


if __name__=='__main__':unittest.main()

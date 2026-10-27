import subprocess
import unittest
from unittest.mock import patch
import collect_cold_start as collector

class CollectorTests(unittest.TestCase):
    def test_extracts_only_expected_status_fields(self):
        raw=b'''<script>var _uptime="42";var ApCliConnStatus="Connected;private-network";</script>
        <td id="drv_chan0">9</td><td id="drv_client0">2</td>v28K.RPT.20220716
        02:00:00:00:00:01 <input value="secret-password-do-not-store">'''
        result=collector.parse_ap_status(raw)
        self.assertEqual(result['upstream_state'],'Connected')
        self.assertEqual(result['channel'],9)
        self.assertEqual(result['uptime_seconds'],42)
        self.assertTrue(result['known_device_mac_present'])
        self.assertNotIn('private-network',str(result))
        self.assertNotIn('secret-password',str(result))

    def test_login_or_missing_telemetry_never_becomes_connected(self):
        result=collector.parse_ap_status(b'<title>Login</title>')
        self.assertIsNone(result['upstream_state'])
        self.assertIsNone(result['channel'])
        self.assertFalse(result['known_device_mac_present'])

    def test_curl_is_credential_free_get_and_discards_body(self):
        output=b'secret-body\n__COLD_START_META__{"http_code":401,"peer":"192.168.1.2","connect_seconds":0.01,"total_seconds":0.02}'
        with patch.object(collector,'command',return_value=(0,output,'')) as call:
            result=collector.get_http('http://192.168.1.2:8080/status.htm',True)
        argv,timeout=call.call_args.args
        self.assertEqual(argv[:2],['/usr/bin/curl','-q'])
        self.assertNotIn('-L',argv)
        self.assertNotIn('--user',argv)
        self.assertNotIn('--cookie',argv)
        self.assertNotIn('POST',argv)
        self.assertLessEqual(timeout,5)
        self.assertEqual(result['http_code'],401)
        self.assertNotIn('secret-body',str(result))
        self.assertNotIn('upstream_state',result)

    def test_bad_metadata_is_not_a_successful_request(self):
        with patch.object(collector,'command',return_value=(7,b'','connect failed')):
            result=collector.get_http('http://192.168.1.2:8080/status.htm',True)
        self.assertIsNone(result['http_code'])
        self.assertEqual(result['curl_exit'],7)
        self.assertNotIn('upstream_state',result)

    def test_rejects_non_lan_targets_and_credential_urls(self):
        for value in ['8.8.8.8','127.0.0.1','169.254.1.1','0.0.0.0','224.0.0.1','example.com']:
            with self.assertRaises(ValueError):collector.private_ipv4(value)
        for value in ['http://admin:password@192.168.1.2','http://192.168.1.2/setok.htm','http://192.168.1.2/?CMD=SYS_CONF','https://192.168.1.2']:
            with self.assertRaises(ValueError):collector.ap_address(value)
        self.assertEqual(collector.ap_address('http://192.168.1.2:8080/'),'http://192.168.1.2:8080')

    def test_hung_child_has_a_bounded_failure(self):
        with patch.object(subprocess,'run',side_effect=subprocess.TimeoutExpired(['curl'],5)):
            code,data,error=collector.command(['curl'],5)
        self.assertIsNone(code)
        self.assertEqual(data,b'')
        self.assertIn('terminated and waited',error)

if __name__=='__main__':unittest.main()

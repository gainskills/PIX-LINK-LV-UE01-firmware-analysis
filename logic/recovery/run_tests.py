"""Offline tests by default; --loopback adds a local-only TCP fixture, never the AP."""
import argparse,json,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--loopback',action='store_true');args=p.parse_args()
modules=['test_flash_backup','test_safe_read','test_full_backup','test_verify_full']
if args.loopback:modules.append('test_transport_local')
suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
result=unittest.TextTestRunner(verbosity=2).run(suite)
report={'status':'PASS' if result.wasSuccessful() else 'FAIL','utc':datetime.now(timezone.utc).isoformat(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'modules':modules,'ap_access':False,'loopback_fixture':args.loopback}
root=Path(__file__).resolve().parent
(root/('test-results.json' if args.loopback else 'offline-test-results.json')).write_text(json.dumps(report,indent=2)+'\n')
sys.exit(0 if result.wasSuccessful() else 1)

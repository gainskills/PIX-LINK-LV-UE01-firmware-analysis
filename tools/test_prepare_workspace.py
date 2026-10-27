"""Offline regression for private evidence path relocation."""
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('prepare_workspace',Path(__file__).with_name('prepare_workspace.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class WorkspaceRelocationTests(unittest.TestCase):
    def test_private_evidence_uses_new_workspace_without_old_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);private=root/'.private/workbench';capture=private/'deployment/private-captures/sample'
            capture.mkdir(parents=True);(capture/'after-profile.private.bin').write_bytes(b'private fixture')
            old='/former/project/firmware-analysis/ap-192.168.1.2/deployment/private-captures/sample'
            original=json.dumps(dict(private_evidence_directory=old,private_marker='retained locally'))
            (private/'deployment/startup-trace-install-attempt.json').write_text(original)
            public=root/'analysis/deployment/startup-trace-install-attempt.json';public.parent.mkdir(parents=True)
            public.write_text(json.dumps(dict(private_evidence_directory='<LEGACY_WORKSPACE>/firmware-analysis/ap-192.168.1.2/deployment/private-captures/sample')))
            (root/'workspace-map.json').write_text(json.dumps(dict(files=[dict(repository_path='analysis/deployment/startup-trace-install-attempt.json',workspace_path='deployment/startup-trace-install-attempt.json',sha256='unused')])) )
            before=hashlib.sha256((private/'deployment/startup-trace-install-attempt.json').read_bytes()).hexdigest()
            previous=module.ROOT;module.ROOT=root
            try:dest=module.prepare(True)
            finally:module.ROOT=previous
            result=json.loads((dest/'deployment/startup-trace-install-attempt.json').read_text())
            self.assertEqual(result.get('private_marker'),'retained locally')
            self.assertEqual(Path(result['private_evidence_directory']),dest/'deployment/private-captures/sample')
            self.assertTrue((Path(result['private_evidence_directory'])/'after-profile.private.bin').is_file())
            self.assertEqual(hashlib.sha256((private/'deployment/startup-trace-install-attempt.json').read_bytes()).hexdigest(),before)

    def test_public_prepare_does_not_copy_private_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'.private/workbench/secret';p.parent.mkdir(parents=True);p.write_text('local')
            (root/'workspace-map.json').write_text('{"files":[]}')
            previous=module.ROOT;module.ROOT=root
            try:dest=module.prepare(False)
            finally:module.ROOT=previous
            self.assertFalse((dest/'secret').exists())

if __name__=='__main__':unittest.main(verbosity=2)

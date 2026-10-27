"""Assemble an ignored offline workspace; never contacts or flashes a device."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def inside(base,relative):
    rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe manifest path')
    path=base/rel
    if not path.resolve().is_relative_to(base.resolve()):raise ValueError('Path escapes workspace')
    return path

def prepare(include_private=False):
    dest=ROOT/'.work';marker=dest/'.repeater-workspace.json'
    if dest.is_symlink():raise ValueError('Workspace must not be a symlink')
    if dest.exists() and any(dest.iterdir()) and not marker.is_file():raise ValueError('Refusing to overwrite an unrelated directory')
    if marker.is_file() and json.loads(marker.read_text()).get('private_inputs') and not include_private:
        raise ValueError('Existing workspace contains private evidence; use --include-private to preserve it')
    dest.mkdir(exist_ok=True)
    if include_private:
        private=ROOT/'.private/workbench'
        if not private.is_dir():raise ValueError('Local private snapshot is unavailable')
        shutil.copytree(private,dest,dirs_exist_ok=True)
    manifest=json.loads((ROOT/'workspace-map.json').read_text())
    for item in manifest['files']:
        src=inside(ROOT,item['repository_path']);out=inside(dest,item['workspace_path'])
        if src.is_relative_to(ROOT/'.private'):raise ValueError('Public map must not include private inputs')
        if src.suffix in ('.bin','.elf') and hashlib.sha256(src.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Firmware/input hash differs: '+item['repository_path'])
        # Local installation records need their original private evidence fields.
        # Sanitized public summaries must not overwrite those local JSON records.
        if include_private and src.suffix=='.json' and (private/item['workspace_path']).is_file():
            continue
        out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)
    if include_private:
        def relocate(value):
            if isinstance(value,dict):return {key:relocate(v) for key,v in value.items()}
            if isinstance(value,list):return [relocate(v) for v in value]
            if isinstance(value,str):
                legacy='/firmware-analysis/ap-192.168.1.2'
                if (value.startswith('/') or value.startswith('<LEGACY_WORKSPACE>')) and legacy in value:
                    return str(dest)+value.split(legacy,1)[1]
                prefix=str(private)
                if value==prefix or value.startswith(prefix+'/'):return str(dest)+value[len(prefix):]
            return value
        for path in dest.rglob('*.json'):
            try:original=json.loads(path.read_text())
            except (ValueError,UnicodeError):continue
            updated=relocate(original)
            if updated!=original:path.write_text(json.dumps(updated,indent=2)+'\n')
    marker.write_text(json.dumps(dict(schema=1,private_inputs=include_private,public_files=len(manifest['files'])),indent=2)+'\n')
    print('Prepared '+str(dest)+'; private inputs '+('included' if include_private else 'excluded'))
    return dest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-private',action='store_true',help='Local only: add captured backup/profile/evidence files; ignored by Git')
    prepare(parser.parse_args().include_private)

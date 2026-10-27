"""Original event-0x20 debounce/edge branch. No network or AP operations.

Query output and timer operations are modeled; downstream reconfiguration is not executed.
"""
import json
from pathlib import Path
from emulate_uplink_monitor import B, SHA, reg, put, get
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
ROOT = Path(__file__).resolve().parent
BASE = 0x80210000

def trial(counter, previous, queried):
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0, 0x300000); u.mem_write(0x400, B)
    u.reg_write(reg('sp'), 0x802f0000)
    u.reg_write(reg('s7'), BASE); u.reg_write(reg('s6'), BASE)
    u.reg_write(reg('s1'), 0x20); u.reg_write(reg('v1'), counter)
    put(u, BASE + 0x5144, counter); u.mem_write(0x215140, bytes([previous]))
    calls = []; done = []
    def returned(value=0):
        u.reg_write(reg('v0'), value & 0xffffffff)
        u.reg_write(reg('pc'), u.reg_read(reg('ra')))
    def code(uc, address, size, unused):
        if address == 0x8011e244:
            args = [u.reg_read(reg(n)) for n in ['a0','a1','a2']]
            assert args == [0x80004908, 0x20, 50]
            calls.append({'call':'schedule_event','event':32,'delay_argument':50}); returned()
        elif address == 0x8011dfdc:
            assert u.reg_read(reg('a0')) == 0x80004908 and u.reg_read(reg('a1')) == 32
            calls.append({'call':'cancel_event','event':32}); returned()
        elif address == 0x80003a3c:
            interface, request, output = [u.reg_read(reg(n)) for n in ['a0','a1','a2']]
            assert interface == 0x8025e740 and request == 0xc0306982
            calls.append({'call':'interface_query','interface_name_pointer':hex(interface),'request':hex(request)})
            put(u, output, queried); returned()
        elif address == 0x800049bc:
            done.append(True); u.emu_stop()
    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(0x80004c8c, 0x802f1000, timeout=3000000, count=10000)
    assert done == [True]
    result={'counter_before':counter,'previous_carrier':previous,'modeled_query_output':queried,
            'calls':calls,'counter_after':get(u,BASE+0x5144),
            'stored_carrier_after':u.mem_read(0x215140,1)[0],
            'output_event_bits':hex(u.reg_read(reg('s1')))}
    if counter < 8:
        assert len(calls)==1 and calls[0]['call']=='schedule_event'
        assert result['counter_after']==counter+1 and result['output_event_bits']=='0x20'
        assert result['stored_carrier_after']==previous
    else:
        assert [c['call'] for c in calls]==['cancel_event','interface_query']
        assert result['counter_after']==6 and result['stored_carrier_after']==queried
        assert result['output_event_bits']==hex(0x204 if previous==0 and queried==1 else 0x208 if previous==1 and queried==0 else 0x20)
    return result

if __name__=='__main__':
    cases=[trial(n,0,1) for n in [0,7]]+[trial(8,p,q) for p in [0,1] for q in [0,1]]
    result={'status':'PASS: six original event-branch cases; query/timers modeled','source_sha256':SHA,
            'entry':'0x80004c8c','cases':cases,
            'limits':['Only executes the event debounce/carrier-edge branch until 0x800049bc.',
                      'The queried interface name and live carrier were not obtained from RAM.',
                      'No full event worker, downstream network reconfiguration, MAT cleanup or hardware recovery emulated.',
                      'Scheduling arguments 50/100 do not establish calibrated wall-clock units.',
                      'No AP access or firmware/configuration changes.']}
    (ROOT/'ethernet-event-experiment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'cases':len(cases),'query_interface_pointer':'0x8025e740'},indent=2))

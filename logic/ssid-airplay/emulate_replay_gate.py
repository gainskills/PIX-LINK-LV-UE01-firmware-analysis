"""Offline original replay-counter branch experiment; no network or crypto bypass test."""
import json
from pathlib import Path
from emulate_uplink_monitor import B, SHA, reg
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
ROOT = Path(__file__).resolve().parent

def trial(current, received):
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0, 0x300000); u.mem_write(0x400, B)
    u.reg_write(reg('sp'), 0x802f0000)
    u.reg_write(reg('s1'), 0x802d0000)
    u.reg_write(reg('s2'), 0x802e0000)
    u.reg_write(reg('s4'), 3)
    u.mem_write(0x2d0009, received.to_bytes(8, 'big'))
    u.mem_write(0x2e0201, current.to_bytes(8, 'big'))
    outcome = []
    def code(uc, address, size, unused):
        if address in [0x8008d3bc, 0x8008d654]:
            outcome.append('passes_counter_gate' if address == 0x8008d3bc else 'rejected_counter')
            u.emu_stop()
    u.hook_add(UC_HOOK_CODE, code)
    u.emu_start(0x8008d550, 0x802f1000, timeout=3000000, count=10000)
    assert len(outcome) == 1
    expected = 'passes_counter_gate' if received > current or received == 0 else 'rejected_counter'
    assert outcome[0] == expected, (current, received, outcome)
    return {'stored_counter': current, 'received_counter': received, 'result': outcome[0]}

if __name__ == '__main__':
    cases = [trial(a, b) for a, b in [(9,10),(9,9),(9,8),(9,0),(0,0),(255,256),(256,255),(0,0xffffffffffffffff)]]
    result = {'status': 'PASS: eight original counter-gate experiments', 'source_sha256': SHA,
              'gate_entry': '0x8008d550', 'native_compare': '0x8006b3a4', 'message_type': 3,
              'cases': cases,
              'limits': ['Executes only the counter comparison branch and native comparator.',
                         'Does not execute full EAPOL length, MIC, nonce, key parsing, replay storage or callers.',
                         'Passing this gate does not imply a frame is accepted or a PHY reset occurs.',
                         'No real packets injected, no AP access or firmware changes.']}
    (ROOT/'replay-gate-experiment.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status':result['status'],'equal_nonzero_counter':cases[1]['result'],
                      'older_nonzero_counter':cases[2]['result'],'zero_counter':cases[3]['result']},indent=2))

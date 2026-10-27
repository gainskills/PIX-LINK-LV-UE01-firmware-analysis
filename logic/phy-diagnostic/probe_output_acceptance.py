"""Offline acceptance fixtures from the written candidate and existing Machine.

Experiment only: not a production console parser or a live-device collector.
"""
import hashlib,json,struct
from pathlib import Path
from test_patch import Machine,reg,RET,GPIO,PCR0,PCR1
from unicorn import UC_HOOK_MEM_READ
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'original-baseline'


def signed(v):return v if v<0x80000000 else v-0x100000000


def sample(main,blob,name,kwargs,initial=0,trace=False,busy_after=None):
    m=Machine(**kwargs);assert m.blob==blob
    m.u.mem_write(0x400,main)
    m.u.mem_write(m.sym['counter']&0x1fffffff,struct.pack('<II',initial,0x87654321))
    if busy_after is not None:
        def contention(uc,access,address,size,value,unused):
            if address&0x1fffffff==PCR1 and len(m.commands)==busy_after:
                uc.mem_write(PCR0,struct.pack('<I',0x4000))
        m.u.hook_add(UC_HOOK_MEM_READ,contention)
    if trace:
        m.sym['entry']=0x80017134;m.run('entry',0x8001713c)
        m.u.reg_write(reg('sp'),0x802f0000);m.u.reg_write(reg('ra'),RET)
    m.cli(['phy']);m.sym['callback']=struct.unpack_from('<I',main,0x211ff0)[0];m.run('callback')
    lines=[];reads=[];summary=None
    for fmt,args in m.prints:
        if fmt=='PHYDIAG relink_calls=%u last_cp0_count=%u\n':
            summary={'relink_calls':args[0],'last_cp0_count':args[1]}
            lines.append('PHYDIAG relink_calls=%u last_cp0_count=%u\n'%(args[0],args[1]))
        elif fmt=='PHYDIAG p0 reg=%u result=%d hex=%04x\n':
            value=signed(args[1]);assert args[1]==args[2]
            reads.append({'register':args[0],'signed_result':value,'hex':format(args[2],'04x')})
            lines.append('PHYDIAG p0 reg=%u result=%d hex=%04x\n'%(args[0],value,args[2]))
        else:raise AssertionError('Unexpected native printf format')
    assert summary is not None and reads
    assert summary['relink_calls']==((initial+1)&0xffffffff if trace else initial)
    sequence=[0,1,1,4,5,6]
    assert [r['register'] for r in reads]==sequence[:len(reads)]
    errors=[i for i,r in enumerate(reads) if r['signed_result']<0]
    if errors:
        assert errors==[len(reads)-1] and reads[-1]['signed_result'] in (-2,-3)
        assert len(reads)==(busy_after+1 if busy_after is not None else 1)
        acceptance='MDIO_ERROR: preserve available prefix; no complete link-state conclusion'
    else:
        assert len(reads)==6 and all(0<=r['signed_result']<=65535 for r in reads)
        acceptance='COMPLETE_RAW_SAMPLE'
    assert m.u.reg_read(reg('cp0_status'))==m.status and m.value(GPIO)==m.mux
    assert m.u.reg_read(reg('sp'))==0x802f0000
    assert all(command&0x6000==0x4000 for command in m.commands)
    return {'case':name,'modeled_input':kwargs,'modeled_busy_after_completed_reads':busy_after,
            'initial_relink_counter':initial,'one_trace_entry_executed':trace,'summary':summary,
            'reads_in_native_order':reads,'rendered_native_output':''.join(lines),'acceptance':acceptance,
            'cp0_status_and_pinmux_restored':True,'phy_configuration_writes':0,
            'bmsr_output_rows':sum(r['register']==1 for r in reads),
            'mdio_read_commands':len(m.commands)}


def main():
    main=(OUT/'main-phy-diagnostic.NOT-FOR-FLASHING.bin').read_bytes()
    assert hashlib.sha256(main).hexdigest()=='0ccb104d36fe70b0c5411979eda687519c0395642efb6ff22a168b40ec5251fe'
    blob=(OUT/'payload.bin').read_bytes()
    cases=[sample(main,blob,'bmsr_first_low_second_high',{'values':[0x3300,0x7809,0x782d,0x5e1,0xc5e1,1]}),
           sample(main,blob,'bmsr_both_low',{'values':[0x3300,0x7809,0x7809,0x5e1,0,0]}),
           sample(main,blob,'all_zero_values_are_valid_results',{'values':[0,0,0,0,0,0]}),
           sample(main,blob,'controller_busy',{'busy':0x4000}),sample(main,blob,'mdio_timeout',{'never':True}),
           sample(main,blob,'counter_reaches_uint32_max',{},0xfffffffe,True),
           sample(main,blob,'counter_wraps_to_zero',{},0xffffffff,True),
           sample(main,blob,'second_bmsr_read_busy',{'values':[0x3300,0x7809]},busy_after=2)]
    assert cases[0]['reads_in_native_order'][1]['signed_result']!=cases[0]['reads_in_native_order'][2]['signed_result']
    assert cases[3]['reads_in_native_order'][0]['hex']=='fffffffe'
    assert cases[4]['reads_in_native_order'][0]['hex']=='fffffffd'
    assert cases[5]['summary']['relink_calls']==0xffffffff and cases[6]['summary']['relink_calls']==0
    assert cases[7]['reads_in_native_order'][-1]['signed_result']==-2 and cases[7]['mdio_read_commands']==2
    report={'status':'PASS: eight candidate-output acceptance cases','candidate_main_sha256':hashlib.sha256(main).hexdigest(),
            'payload_sha256':hashlib.sha256(blob).hexdigest(),'cases':cases,
            'limits':['Actual written candidate callback/payload execute with existing test_patch.Machine models.',
                      'MMIO, printf and CP0 Count are synthetic; console text is rendered from native format/arguments.',
                      'Mid-query contention is an injected controller-busy condition between transactions.',
                      'Does not execute Telnet transport, CLI tokenizer, original relink body or real PHY reads.',
                      'Counter zero cannot distinguish boot/reset from wrap without uptime/context.',
                      'No production parser or new live query tool added; this is an offline acceptance fixture.',
                      'No AP access, configuration changes, firmware image changes or Flash operations.']}
    (OUT/'diagnostic-output-acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])
    print(cases[-1]['rendered_native_output'],end='')


if __name__=='__main__':main()

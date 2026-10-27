"""Offline MIPS32 LE diagnostic payload. No network or live device operations."""
import struct
BASE=0x80000400
START=0x8019f0c4
REG_HANDLER=0x80112960
PRINTF=0x8014fca8
RELINK=0x80017134
CALLBACK=0x802123f0

class Assembler:
    """Small explicit encoder; independent Capstone/Unicorn checks accompany it."""
    regs={name:i for i,name in enumerate('z at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split())}
    def __init__(self):self.data=bytearray();self.symbols={};self.fixups=[]
    def emit(self,w):self.data+=struct.pack('<I',w)
    def label(self,n):self.symbols[n]=START+len(self.data)
    def i(self,op,rt,rs,imm):self.emit(op<<26|self.regs[rs]<<21|self.regs[rt]<<16|(imm&65535))
    def r(self,fn,rd,rs,rt='z',sa=0):self.emit(self.regs[rs]<<21|self.regs[rt]<<16|self.regs[rd]<<11|sa<<6|fn)
    def move(self,d,s):self.r(33,d,s)
    def li(self,d,v):self.i(15,d,'z',v>>16);self.i(13,d,d,v&65535)
    def address(self,d,s):self.fixups.append((len(self.data),'addr',s));self.li(d,0)
    def branch(self,op,rs,rt,s):self.fixups.append((len(self.data),'branch',s));self.i(op,rt,rs,0);self.emit(0)
    def jump(self,target,call=False):
        if isinstance(target,str):self.fixups.append((len(self.data),'jump',target));target=0
        self.emit((3 if call else 2)<<26|((target>>2)&0x3ffffff));self.emit(0)
    def cp0(self,rt,number=12,write=False):self.emit(0x40000000|(4<<21 if write else 0)|self.regs[rt]<<16|number<<11)
    def hazards(self):self.emit(0);self.emit(0);self.emit(0)
    def ret(self):self.r(8,'z','ra');self.emit(0)
    def finish(self):
        for offset,kind,name in self.fixups:
            target=self.symbols[name];w=struct.unpack_from('<I',self.data,offset)[0]
            if kind=='branch':
                delta=(target-(START+offset+4))//4
                assert -32768<=delta<=32767
                w|=delta&65535
            elif kind=='jump':w|=(target>>2)&0x3ffffff
            else:
                w|=target>>16
                struct.pack_into('<I',self.data,offset+4,struct.unpack_from('<I',self.data,offset+4)[0]|(target&65535))
            struct.pack_into('<I',self.data,offset,w)
        return bytes(self.data),dict(self.symbols)

def assemble():
    a=Assembler();a.label('reader')
    # a0=PHY 0..4, a1=standard register 0..6. No PHY writes.
    a.i(11,'t5','a0',5);a.branch(4,'t5','z','invalid')
    a.i(11,'t5','a1',7);a.branch(4,'t5','z','invalid')
    a.cp0('t0');a.emit(0);a.i(9,'t5','z',-2);a.r(36,'t5','t0','t5');a.cp0('t5',write=True);a.hazards()
    a.li('t3',0xb01100c0);a.i(35,'t5','t3',0);a.i(12,'t5','t5',0x6000);a.branch(5,'t5','z','busy')
    a.li('t1',0xb0000060);a.i(35,'t2','t1',0);a.i(9,'t5','z',-129);a.r(36,'t5','t2','t5');a.i(43,'t5','t1',0)
    a.r(0,'t5','z','a1',8);a.i(13,'t5','t5',0x4000);a.r(37,'t5','t5','a0');a.i(43,'t5','t3',0)
    a.i(9,'t4','t3',4);a.i(15,'t6','z',1)
    a.label('poll');a.i(35,'t7','t4',0);a.i(12,'t5','t7',2);a.branch(5,'t5','z','success');a.i(9,'t6','t6',-1);a.branch(5,'t6','z','poll')
    a.i(9,'v0','z',-3);a.jump('cleanup')
    a.label('success');a.r(2,'v0','z','t7',16)
    a.label('cleanup');a.i(43,'t2','t1',0);a.jump('restore')
    a.label('busy');a.i(9,'v0','z',-2)
    a.label('restore');a.cp0('t0',write=True);a.hazards();a.ret()
    a.label('invalid');a.i(9,'v0','z',-1);a.ret()
    a.label('reader_end')

    # Exact 'reg phy' only; legacy path never changes SP/arguments/RA.
    a.label('wrapper');a.i(9,'t0','z',1);a.branch(5,'a0','t0','legacy');a.i(35,'t0','a1',0)
    for off,char in enumerate(b'phy\0'):
        a.i(36,'t1','t0',off);a.i(9,'t2','z',char);a.branch(5,'t1','t2','legacy')
    a.i(9,'sp','sp',-40)
    for n,off in [('ra',36),('s0',32),('s1',28),('s2',24),('s3',20)]:a.i(43,n,'sp',off)
    # Snapshot count and last tick atomically before formatted output.
    a.cp0('t0');a.emit(0);a.i(9,'t1','z',-2);a.r(36,'t1','t0','t1');a.cp0('t1',write=True);a.hazards()
    a.address('t2','counter');a.i(35,'a1','t2',0);a.i(35,'a2','t2',4)
    a.cp0('t0',write=True);a.hazards();a.address('a0','summary_fmt');a.jump(PRINTF,True)
    a.address('s0','registers');a.i(9,'s1','z',6)
    a.label('query');a.i(36,'s2','s0',0);a.move('a0','z');a.move('a1','s2');a.jump('reader',True);a.move('s3','v0')
    a.address('a0','value_fmt');a.move('a1','s2');a.move('a2','s3');a.move('a3','s3');a.jump(PRINTF,True)
    a.r(42,'t0','s3','z');a.branch(5,'t0','z','done');a.i(9,'s0','s0',1);a.i(9,'s1','s1',-1);a.branch(5,'s1','z','query')
    a.label('done')
    for n,off in [('ra',36),('s0',32),('s1',28),('s2',24),('s3',20)]:a.i(35,n,'sp',off)
    a.i(9,'sp','sp',40);a.move('v0','z');a.ret()
    a.label('legacy');a.jump(REG_HANDLER)
    a.label('wrapper_end')

    # Relink entry trampoline: preserve all scratch state before replaying prologue.
    a.label('trace');a.i(9,'sp','sp',-24)
    for i,n in enumerate(['t0','t1','t2','t3']):a.i(43,n,'sp',i*4)
    a.cp0('t0');a.emit(0);a.i(9,'t1','z',-2);a.r(36,'t1','t0','t1');a.cp0('t1',write=True);a.hazards()
    a.address('t1','counter');a.i(35,'t2','t1',0);a.i(9,'t2','t2',1);a.i(43,'t2','t1',0)
    a.label('read_count');a.cp0('t3',9);a.emit(0);a.i(43,'t3','t1',4)
    a.cp0('t0',write=True);a.hazards()
    for i,n in enumerate(['t0','t1','t2','t3']):a.i(35,n,'sp',i*4)
    a.i(9,'sp','sp',24)
    a.emit(0x27bdffe8);a.emit(0x3c028017);a.jump(RELINK+8)
    a.label('code_end')
    a.label('counter');a.data+=b'\0'*8
    a.label('registers');a.data+=bytes([0,1,1,4,5,6])+b'\0'*2
    a.label('summary_fmt');a.data+=b'PHYDIAG relink_calls=%u last_cp0_count=%u\n\0'
    a.label('value_fmt');a.data+=b'PHYDIAG p0 reg=%u result=%d hex=%04x\n\0'
    while len(a.data)%4:a.data+=b'\0'
    a.label('end');return a.finish()

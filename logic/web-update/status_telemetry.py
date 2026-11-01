"""Read-only status renderer: export the same association state as vendor index."""
import struct
BASE=0x80000400
CALL=0x8000ac68-BASE
OFFSET=0x19f340  # Zero retired-image storage, beyond startup-trace end 0x19f33c.
ADDRESS=BASE+OFFSET
STATE=0x802551d0
WRITER=0x80011e74
# Tail-call preserves the status renderer's return address, SP and saved registers.
WORDS=(0x3c068025,0x8cc651d0,0x3c058016,0x24a56aac,
       0x08000000|((WRITER>>2)&0x3ffffff),0)
PAYLOAD=struct.pack('<6I',*WORDS)
def apply(main):
    if struct.unpack_from('<II',main,CALL)!=(0x0c002e32,0x02002021):
        raise ValueError('Unexpected status output call/delay slot')
    if main[OFFSET:OFFSET+len(PAYLOAD)]!=bytes(len(PAYLOAD)):
        raise ValueError('Status telemetry storage occupied')
    if main[0x80166aac-BASE:0x80166aac-BASE+3]!=b'%u\0':
        raise ValueError('Unexpected native numeric formatter')
    out=bytearray(main);out[OFFSET:OFFSET+len(PAYLOAD)]=PAYLOAD
    struct.pack_into('<I',out,CALL,0x0c000000|((ADDRESS>>2)&0x3ffffff))
    return out,[[CALL,CALL+4],[OFFSET,OFFSET+len(PAYLOAD)]]

"""Bounded acquisition of clean, address-mappable rows. Never strips log text."""
from flash_backup import partial_read,read_command

def collect_rows(read,address,count,label,chunk=1024):
    if count<=0 or count%16 or chunk<=0 or chunk%16 or chunk>16384 or address<0 or address%16 or address+count>0x200000:raise ValueError('Invalid acquisition window')
    def segment(start,length,tag):
        read_command(start,length)
        for attempt in range(2):
            raw=read(start,length,f'{tag}-{attempt}')
            try:return partial_read(raw,length)
            except ValueError:pass
        if length==16:raise ValueError(f'Unmappable 16-byte response at {start:#x}')
        half=((length//2)//16)*16
        return segment(start,half,tag+'L')+segment(start+half,length-half,tag+'R')
    rows=[]
    for offset in range(0,count,chunk):rows.extend(segment(address+offset,min(chunk,count-offset),f'{label}-{offset:x}'))
    return rows

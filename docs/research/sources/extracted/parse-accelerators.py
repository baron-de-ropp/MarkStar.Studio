import pefile, struct, sys

VK = {0x08:'Backspace',0x09:'Tab',0x0D:'Enter',0x1B:'Esc',0x20:'Space',0x21:'PgUp',0x22:'PgDn',
0x23:'End',0x24:'Home',0x25:'Left',0x26:'Up',0x27:'Right',0x28:'Down',0x2D:'Insert',0x2E:'Delete',
0x70:'F1',0x71:'F2',0x72:'F3',0x73:'F4',0x74:'F5',0x75:'F6',0x76:'F7',0x77:'F8',0x78:'F9',
0x79:'F10',0x7A:'F11',0x7B:'F12',0x2C:'PrintScreen',0x13:'Pause',0x6A:'Num*',0x6B:'Num+',0x6D:'Num-',0x6F:'Num/'}
def kn(k):
    if k in VK: return VK[k]
    if 0x30<=k<=0x5A: return chr(k)
    return f'VK_0x{k:02X}'

FVIRTKEY,FNOINVERT,FSHIFT,FCONTROL,FALT = 1,2,4,8,16

for path in sys.argv[1:]:
    pe = pefile.PE(path)
    print(f'===== {path} =====')
    if not hasattr(pe,'DIRECTORY_ENTRY_RESOURCE'): print('no resources'); continue
    for e in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if e.id != 9: continue   # RT_ACCELERATOR
        for tbl in e.directory.entries:
            name = tbl.name if tbl.name else tbl.id
            for lang in tbl.directory.entries:
                d = lang.data.struct
                data = pe.get_memory_mapped_image()[d.OffsetToData:d.OffsetToData+d.Size]
                print(f'--- ACCELERATOR table {name} ({d.Size} bytes) ---')
                off=0
                while off+8 <= len(data):
                    fl,key,cmd,_pad = struct.unpack_from('<HHHH', data, off); off+=8
                    mods=[]
                    if fl&FCONTROL: mods.append('Ctrl')
                    if fl&FALT: mods.append('Alt')
                    if fl&FSHIFT: mods.append('Shift')
                    combo='+'.join(mods+[kn(key) if fl&FVIRTKEY else repr(chr(key&0xFF))])
                    print(f'  {combo:<28} cmd={cmd}')
                    if fl & 0x80: break   # last entry

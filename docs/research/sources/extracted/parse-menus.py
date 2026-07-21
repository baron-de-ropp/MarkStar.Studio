import pefile, struct, sys
MF_POPUP, MF_END = 0x0010, 0x0080
def rdstr(d, off):
    s=[]
    while off+2<=len(d):
        c,=struct.unpack_from('<H',d,off); off+=2
        if c==0: break
        s.append(chr(c))
    return ''.join(s), off

def parse(d, off, depth, out):
    while off < len(d):
        if off+2>len(d): break
        flags,=struct.unpack_from('<H',d,off)
        if flags & MF_POPUP:
            off+=2
            txt,off = rdstr(d,off)
            out.append(('  '*depth)+f'[{txt}]')
            off = parse(d,off,depth+1,out)
        else:
            if off+4>len(d): break
            flags,mid = struct.unpack_from('<HH',d,off); off+=4
            txt,off = rdstr(d,off)
            label = txt.replace('\t',' \\t ') if txt else '---separator---'
            out.append(('  '*depth)+f'{label}   (id={mid})')
        if flags & MF_END: break
    return off

pe = pefile.PE(sys.argv[1])
for e in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    if e.id != 4: continue
    for tbl in e.directory.entries:
        name = tbl.name if tbl.name else tbl.id
        for lang in tbl.directory.entries:
            st = lang.data.struct
            d = pe.get_memory_mapped_image()[st.OffsetToData:st.OffsetToData+st.Size]
            ver,hs = struct.unpack_from('<HH', d, 0)
            out=[]
            parse(d, 4+hs, 0, out)
            print(f'===== MENU {name} ({st.Size} bytes) =====')
            print('\n'.join(out)); print()

SECTIONS {
.native_orf_hook 0x60550363 : { *(.native_orf_hook) }
.native_orf_export 0x6071b100 : { *(.native_orf_export) }
}
native_orf_copy = 0x604b0d0b;
hl_owner_row = 0x6071a280;
source_uncached = 0xa0719e00;

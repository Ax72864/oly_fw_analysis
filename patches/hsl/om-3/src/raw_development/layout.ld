SECTIONS {
.raw_acquire_hook 0x618e28ab : { *(.raw_acquire_hook) }
.raw_acquire 0x6071b000 : { *(.raw_acquire) }
}
raw_acquire_resume = 0x618e28b1;
section_mask = 0xa3371164;
hl_source_to_owner = 0x6071a000;
hl_owner_row = 0x6071a000;

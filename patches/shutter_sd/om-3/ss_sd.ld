/* Shutter SD loader — section-1 bank1 head (after shutter code caves). */
ENTRY(ss_chain)

SS_CODE = 0x603244b0;
SS_STATE = 0x60324c00;
PCM_BASE = 0x60324d00;
PCM_LIMIT = 0x60357000;

SECTIONS {
  .text SS_CODE : {
    *(.text .text.*)
    *(.rodata .rodata.*)
    . = ALIGN(4);
    *(.state)
    *(.data .data.*)
  }
  /DISCARD/ : { *(.comment) *(.note*) *(.bss) }
}
ASSERT(. <= SS_STATE + 0x100, "ss_sd image too large for reserved window")

fopen         = 0x608d4d22;
fclose        = 0x608d4d2b;
fseek         = 0x608d4fb1;
ftell         = 0x608d4f47;
fread         = 0x608d4eb7;
fwrite        = 0x608d4da9;

nm_load       = 0x60f49800;   /* real entry; +7 skips the first pointer clear */
sd_out        = 0x60a8f1e2;
stock_cnt     = 0x60b86e09;
stock_vbi     = 0x60b87031;
stock_sel     = 0x60b86a01;
stock_get     = 0x60b86de7;
stock_write   = 0x60b8781f;

selected_slot = 0x60322000;
range_count   = 0x60322050;
range0_lo     = 0x60322054;
range0_hi     = 0x60322058;
desc0_addr    = 0x603220a0;
desc0_len     = 0x603220a4;
desc0b_addr   = 0x603220a8;
desc0b_len    = 0x603220ac;

pcm_base      = PCM_BASE;
pcm_limit     = PCM_LIMIT;

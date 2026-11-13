/*
 * OM-3 electronic-shutter sounds from SD (post-Caduceus SDLOAD).
 *
 * Card files:
 *   C:\OM3MOD\SHUT01.WAV .. SHUT99.WAV  — 48 kHz / 16-bit / stereo PCM RIFF
 *   C:\OM3MOD\SHUTSEL.BIN               — remembered slot index (0 = Off)
 *
 * Hook: Caduceus sd_load replaces `call nm_load; bra sd_out` with `jmp ss_chain`.
 * ss_chain only marks the card load finished. WAV scan/load is lazy, and only
 * for shutter menu ids 6001/6002. Every other id falls through to stock.
 * nm_load entry is the real call target (not +7).
 */
        .text
        .global ss_chain, ss_boot, ss_prepare
        .global ss_option_count, ss_option_value, ss_option_blocked
        .global ss_config_read, ss_config_write
        .global ss_path_template, ss_sel_path

/* ------------------------------------------------------------------ */
/* Entered instead of nm_load+bra from sd_load. a2 = Caduceus P block. */
ss_chain:
        call    nm_load,[d2,d3,a2,a3],36
        mov     1,d0
        mov     d0,(ss_card_ready)
        jmp     sd_out

/* d0=1 when lists/selection are valid; 0 if sd_load has not finished. */
ss_prepare:
        mov     (ss_inited),d0
        cmp     0,d0
        bne     1f
        mov     (ss_card_ready),d0
        cmp     0,d0
        beq     2f
        call    ss_boot,[d2,d3,a2,a3],40
        mov     1,d0
        mov     d0,(ss_inited)
1:
        mov     1,d0
        ret     [d2,d3,a2,a3],8
2:
        clr     d0
        ret     [d2,d3,a2,a3],8

/* ------------------------------------------------------------------ */
/* Scan SHUTxx, restore SHUTSEL, arm native slot0 or Off.               */
/* Frame 40: (4) i, (8) handle, (12) size, (16) selected, (20) tmp     */
ss_boot:
        call    ss_scan,[d2,d3,a2,a3],28
        call    ss_read_sel,[d2,d3,a2,a3],28
        mov     (ss_selected),d0
        cmp     0,d0
        beq     1f
        call    ss_slot_present,[d2,d3,a2,a3],12   /* d0=slot -> d0 0/1 */
        cmp     0,d0
        beq     2f
        mov     (ss_selected),d0
        call    ss_load_slot,[d2,d3,a2,a3],40
        cmp     0,d0
        beq     3f
2:
        clr     d0
        mov     d0,(ss_selected)
1:
        call    ss_arm_off,[d2,d3,a2,a3],8
        bra     4f
3:
        /* armed inside ss_load_slot */
4:
        ret     [d2,d3,a2,a3],40

/* ------------------------------------------------------------------ */
/* Build present list ss_list[0..n) of slot numbers 1..99.              */
ss_scan:
        clr     d0
        mov     d0,(ss_n_present)
        mov     d0,(ss_n_menu)
        mov     1,d0
        mov     d0,(ss_n_menu)          /* Off only until files found */
        mov     1,d2                    /* slot = 1 */
1:
        cmp     100,d2
        bcc     9f
        mov     d2,d0
        call    ss_set_path_digits,[d2,d3,a2,a3],12
        mov     ss_path_template,a0
        mov     ss_mode_r,a1
        call    fopen,[],4
        cmp     0,a0
        beq     2f
        mov     a0,a3
        mov     a3,a0
        call    fclose,[d2,a2,a3],16
        mov     (ss_n_present),d0
        cmp     99,d0
        bcc     9f
        mov     ss_list,a0
        movbu   d2,(d0,a0)
        inc     d0
        mov     d0,(ss_n_present)
        add     1,d0
        mov     d0,(ss_n_menu)
2:
        inc     d2
        bra     1b
9:
        ret     [d2,d3,a2,a3],28

/* d0 = slot 1..99 -> write two ASCII digits into ss_path_template at +12 */
ss_set_path_digits:
        /* path = C:\OM3MOD\SHUT##.WAV  digit offsets 12,13 */
        mov     d0,d1
        mov     10,d2
        /* d0 / 10 -> tens in d3, ones in d1 — simple subtract loop */
        clr     d3
1:
        cmp     d2,d1
        bcs     2f
        sub     d2,d1
        inc     d3
        bra     1b
2:
        add     0x30,d3
        add     0x30,d1
        mov     ss_path_template,a0
        movbu   d3,(12,a0)
        movbu   d1,(13,a0)
        ret     [d2,d3,a2,a3],12

/* d0=slot -> d0=1 if listed in ss_list */
ss_slot_present:
        mov     d0,d2
        clr     d3
        mov     (ss_n_present),d1
1:
        cmp     d1,d3
        bcc     0f
        mov     ss_list,a0
        movbu   (d3,a0),d0
        cmp     d2,d0
        beq     1f
        inc     d3
        bra     1b
1:
        mov     1,d0
        ret     [d2,d3,a2,a3],12
0:
        clr     d0
        ret     [d2,d3,a2,a3],12

/* ------------------------------------------------------------------ */
ss_read_sel:
        mov     ss_sel_path,a0
        mov     ss_mode_r,a1
        call    fopen,[],4
        cmp     0,a0
        beq     9f
        mov     a0,a3
        mov     ss_sel_buf,a0
        mov     1,d0
        mov     12,d1
        mov     a3,a1
        call    fread,[d2,d3,a2,a3],24
        mov     d0,d2
        mov     a3,a0
        call    fclose,[d2,a2,a3],16
        cmp     12,d2
        bne     9f
        mov     (ss_sel_buf),d0
        cmp     0x53334d4f,d0           /* 'OM3S' immediate, not the label address */
        bne     9f
        movhu   (ss_sel_buf+4),d0
        cmp     1,d0
        bne     9f
        movhu   (ss_sel_buf+6),d0
        movhu   (ss_sel_buf+8),d1
        mov     d0,d2
        xor     d1,d2
        xor     0x9bdf,d2
        cmp     0,d2
        bne     9f
        /* accept 0..99 */
        cmp     100,d0
        bcc     9f
        mov     d0,(ss_selected)
        ret     [d2,d3,a2,a3],28
9:
        clr     d0
        mov     d0,(ss_selected)
        ret     [d2,d3,a2,a3],28

/* Write SHUTSEL from ss_selected. Frame 28. */
ss_write_sel:
        mov     0x53334d4f,d0
        mov     d0,(ss_sel_buf)
        mov     1,d0
        movhu   d0,(ss_sel_buf+4)
        mov     (ss_selected),d0
        movhu   d0,(ss_sel_buf+6)
        mov     d0,d1
        xor     0x9bdf,d1
        movhu   d1,(ss_sel_buf+8)
        clr     d0
        movhu   d0,(ss_sel_buf+10)
        mov     ss_sel_path,a0
        mov     ss_mode_w,a1
        call    fopen,[],4
        cmp     0,a0
        beq     9f
        mov     a0,a3
        mov     ss_sel_buf,a0
        mov     1,d0
        mov     12,d1
        mov     a3,a1
        call    fwrite,[d2,d3,a2,a3],24
        mov     a3,a0
        call    fclose,[d2,a2,a3],16
9:
        ret     [d2,d3,a2,a3],28

/* ------------------------------------------------------------------ */
/* Load SHUT{d0}.WAV into pcm_base; update descriptors; selected_slot=0 */
/* Returns d0=0 ok, nonzero fail. Frame 40. */
ss_load_slot:
        mov     d0,(4,sp)               /* slot */
        call    ss_set_path_digits,[d2,d3,a2,a3],12
        mov     ss_path_template,a0
        mov     ss_mode_r,a1
        call    fopen,[],4
        cmp     0,a0
        beq     bad
        mov     a0,(8,sp)
        /* size via SEEK_END (0=SET, 1=CUR, 2=END) */
        clr     d0
        mov     2,d1
        call    fseek,[d2,d3,a2,a3],20
        cmp     0,d0
        bne     bad_close
        mov     (8,sp),a0
        call    ftell,[d2,a2,a3],16
        mov     d0,(12,sp)
        cmp     44,d0
        bcs     bad_close
        mov     pcm_limit,d1
        mov     pcm_base,d2
        sub     d2,d1                   /* max bytes */
        cmp     d1,d0
        bcc     bad_close               /* size >= max */
        /* rewind */
        mov     (8,sp),a0
        clr     d0
        clr     d1                     /* SEEK_SET */
        call    fseek,[d2,d3,a2,a3],20
        cmp     0,d0
        bne     bad_close
        mov     pcm_base,a0
        mov     1,d0
        mov     (12,sp),d1
        mov     (8,sp),a1
        call    fread,[d2,d3,a2,a3],24
        mov     d0,d3
        mov     (8,sp),a0
        call    fclose,[d2,a2,a3],16
        mov     (12,sp),d0
        cmp     d0,d3
        bne     bad
        /* RIFF/WAVE check */
        mov     pcm_base,a0
        mov     (0,a0),d0
        cmp     0x46464952,d0           /* 'RIFF' */
        bne     bad
        mov     (8,a0),d0
        cmp     0x45564157,d0           /* 'WAVE' */
        bne     bad
        mov     (12,a0),d0
        cmp     0x20746d66,d0           /* 'fmt ' */
        bne     bad
        movhu   (20,a0),d0
        cmp     1,d0                    /* PCM */
        bne     bad
        movhu   (22,a0),d0
        cmp     2,d0                    /* stereo */
        bne     bad
        mov     (24,a0),d0
        cmp     48000,d0
        bne     bad
        /* arm descriptors */
        mov     (12,sp),d2              /* wav_len */
        mov     pcm_base,d0
        mov     d0,(desc0_addr)
        mov     d0,(desc0b_addr)
        mov     d2,(desc0_len)
        mov     d2,(desc0b_len)
        mov     1,d0
        mov     d0,(range_count)
        mov     pcm_base,d0
        add     44,d0
        mov     d0,(range0_lo)
        mov     pcm_base,d1
        add     d2,d1
        mov     d1,(range0_hi)
        clr     d0
        mov     d0,(selected_slot)      /* play descriptor 0 */
        clr     d0                      /* success */
        ret     [d2,d3,a2,a3],40

bad_close:
        mov     (8,sp),a0
        call    fclose,[d2,a2,a3],16
bad:
        mov     1,d0
        ret     [d2,d3,a2,a3],40

ss_arm_off:
        clr     d0
        mov     d0,(desc0_len)
        mov     d0,(desc0b_len)
        mov     d0,(range_count)
        mov     3,d0                    /* native Off index in 1/2/3/Off menu */
        mov     d0,(selected_slot)
        ret     [d2,d3,a2,a3],8

/* ------------------------------------------------------------------ */
/* d0 = menu id. 6001/6002 are shutter sound; anything else is stock.   */
/* Count/value/blocked/read use retf [],0 like the caves they replace.  */
ss_option_count:
        cmp     6001,d0
        beq     1f
        cmp     6002,d0
        beq     1f
        jmp     stock_cnt
1:
        call    ss_prepare,[d2,d3,a2,a3],8
        cmp     0,d0
        beq     2f
        mov     (ss_n_menu),d0
        cmp     0,d0
        bne     3f
2:
        mov     1,d0
3:
        retf    [],0

/* d0=id, d1=index, a1=optional out. Value 0=Off, else SHUT slot. */
ss_option_value:
        cmp     6001,d0
        beq     1f
        cmp     6002,d0
        beq     1f
        jmp     stock_vbi
1:
        mov     d1,(ss_save_d1)
        mov     a1,(ss_save_a1)
        call    ss_prepare,[d2,d3,a2,a3],8
        mov     (ss_save_d1),d1
        cmp     0,d0
        beq     2f
        mov     (ss_n_menu),d0
        cmp     d0,d1
        bcc     2f
        cmp     0,d1
        bne     4f
        clr     d0
        bra     5f
4:
        mov     d1,d0
        add     -1,d0
        mov     ss_list,a0
        movbu   (d0,a0),d0
        bra     5f
2:
        cmp     0,d1
        bne     6f
        clr     d0
        bra     5f
6:
        mov     -1,d0
5:
        mov     (ss_save_a1),a1
        cmp     0,a1
        beq     7f
        mov     d0,(a1)
7:
        retf    [],0

/* d0=id, d1=index. d0=0 selectable, 1 blocked. */
ss_option_blocked:
        cmp     6001,d0
        beq     1f
        cmp     6002,d0
        beq     1f
        jmp     stock_sel
1:
        mov     d1,(ss_save_d1)
        call    ss_prepare,[d2,d3,a2,a3],8
        mov     (ss_save_d1),d1
        cmp     0,d0
        beq     2f
        mov     (ss_n_menu),d0
        cmp     d0,d1
        bcc     3f
        clr     d0
        retf    [],0
2:
        cmp     0,d1
        bne     3f
        clr     d0
        retf    [],0
3:
        mov     1,d0
        retf    [],0

/* d0=id, a1=out ptr. Success writes the current value and returns 0. */
ss_config_read:
        cmp     6001,d0
        beq     1f
        cmp     6002,d0
        beq     1f
        jmp     stock_get
1:
        cmp     0,a1
        bne     2f
        mov     -1,d0
        retf    [],0
2:
        mov     a1,(ss_save_a1)
        call    ss_prepare,[d2,d3,a2,a3],8
        mov     (ss_save_a1),a1
        cmp     0,d0
        bne     3f
        clr     d0
        bra     4f
3:
        mov     (ss_selected),d0
4:
        mov     d0,(a1)
        clr     d0
        retf    [],0

/* d0=id, a1=new value (0=Off or slot). Persist + reload, else Off. */
ss_config_write:
        cmp     6001,d0
        beq     1f
        cmp     6002,d0
        beq     1f
        jmp     stock_write
1:
        mov     a1,(ss_save_a1)
        call    ss_prepare,[d2,d3,a2,a3],8
        mov     (ss_save_a1),d0
        mov     d0,(ss_selected)
        mov     (ss_card_ready),d0
        cmp     0,d0
        beq     2f
        call    ss_write_sel,[d2,d3,a2,a3],28
        mov     (ss_selected),d0
        cmp     0,d0
        beq     3f
        call    ss_slot_present,[d2,d3,a2,a3],12
        cmp     0,d0
        beq     3f
        mov     (ss_selected),d0
        call    ss_load_slot,[d2,d3,a2,a3],40
        cmp     0,d0
        beq     2f
3:
        clr     d0
        mov     d0,(ss_selected)
        call    ss_arm_off,[d2,d3,a2,a3],8
2:
        clr     d0
        retf    [],0

/* ------------------------------------------------------------------ */
        .align  2
ss_mode_r:
        .asciz  "r"
        .align  2
ss_mode_w:
        .asciz  "w"
        .align  2
ss_path_template:
        .asciz  "C:\\OM3MOD\\SHUT00.WAV"
        .align  2
ss_sel_path:
        .asciz  "C:\\OM3MOD\\SHUTSEL.BIN"
        .align  2
ss_sel_magic:
        .long   0x53334d4f              /* 'OM3S' */
ss_sel_xor:
        .long   0x00009bdf              /* u16 checksum key */

/* Mutable image-backed state (zeros in firmware until boot). */
        .section .state,"aw"
        .align  2
        .global ss_selected, ss_n_present, ss_n_menu, ss_list, ss_sel_buf
        .global ss_card_ready, ss_inited, ss_save_d1, ss_save_a1
ss_selected:
        .long   0
ss_n_present:
        .long   0
ss_n_menu:
        .long   1
ss_card_ready:
        .long   0
ss_inited:
        .long   0
ss_save_d1:
        .long   0
ss_save_a1:
        .long   0
ss_list:
        .space  100
ss_sel_buf:
        .space  16

/* OM-3 settings backup: type-2 line OM3_HSL_V1 + 48 packed hex nibbles.
 * Export hook is only 4 bytes -> 3-byte jmp + nop.
 */
.section .backup_export_hook,"ax"
 .byte 0xcc
 .short hl_backup_export_hook - (.-1)
 .byte 0x00

.section .backup_header_hook,"ax"
 jmp hl_backup_header_hook
 nop

.section .backup_line_hook,"ax"
 jmp hl_backup_line_hook
 nop

.section .backup_footer_hook,"ax"
 jmp hl_backup_footer_hook
 nop
 nop

.section .backup_export,"ax"
.global hl_backup_export_hook, hl_backup_export

hl_backup_export_hook:
 mov (24,sp),d0
 cmp 2,d0
 bne hl_backup_export_resume
 mov d3,d0
 mov a3,d1
 mov (16,sp),a0
 call hl_backup_export,[d2,d3,a2,a3],32
 cmp 0,d0
 bne hl_backup_export_fail
 add 110,a3
hl_backup_export_resume:
 mov (16,sp),a0
 mov d3,d0
 mov a3,a1
 /* Fall into the stock call that followed the 4-byte hook. */
 jmp native_backup_write3
hl_backup_export_fail:
 clr d3
 jmp native_backup_export_fail

/* d0=bank mask, d1=out offset, a0={base,cap}; emit 2,OM3_HSL_V1,<96 hex>\r\n */
hl_backup_export:
 mov d0,d3
 mov d1,d2
 mov a0,a3
 mov (a0),d0
 add d2,d0
 mov d0,a2
 mov hl_backup_prefix,a1
 mov 14,d0
hl_backup_copy_prefix:
 movbu (a1),d1
 movbu d1,(a2)
 inc a1
 inc a2
 add -1,d0
 bne hl_backup_copy_prefix
 cmp 256,d3
 beq hl_backup_live
 /* non-current bank: still export live ACTIVE as best effort */
hl_backup_live:
 mov 928,d2
hl_backup_loop:
 mov d2,d0
 mov 1,d1
 call stock_active_get,[d2],8
 call hl_decode_cell,[],4
 mov hl_backup_hex,a0
 mov d0,d1
 lsr 4,d1
 movbu (d1,a0),d1
 movbu d1,(a2)
 inc a2
 and 15,d0
 movbu (d0,a0),d0
 movbu d0,(a2)
 inc a2
 inc d2
 cmp 976,d2
 bne hl_backup_loop
 mov 13,d0
 movbu d0,(a2)
 inc a2
 mov 10,d0
 movbu d0,(a2)
 clr d0
 ret [d2,d3,a2,a3],32

.section .backup_lifecycle,"ax"
.global hl_backup_header_hook, hl_backup_footer_hook
hl_backup_header_hook:
 mov (72,sp),d0
 mov hl_backup_state,a0
 mov d0,(0,a0)
 clr d1
 mov d1,(4,a0)
 cmp 256,d0
 jmp native_backup_header_resume

hl_backup_footer_hook:
 mov hl_backup_state,a0
 mov (4,a0),d0
 cmp 1,d0
 bne hl_backup_footer_stock
 call hl_backup_apply,[],4
hl_backup_footer_stock:
 movbu (64,sp),d0
 cmp 255,d0
 jmp native_backup_footer_resume

.section .backup_import,"ax"
.global hl_backup_line_hook, hl_backup_parse, hl_backup_apply
hl_backup_line_hook:
 mov a2,a0
 movhu (84,sp),d0
 call hl_backup_parse,[d2,d3,a2,a3],24
 cmp 1,d0
 beq hl_backup_line_done
 cmp 2,d0
 beq hl_backup_line_bad
 mov a2,a0
 movhu (84,sp),d0
 mov (52,sp),a1
 jmp native_backup_line_resume
hl_backup_line_done:
 jmp native_backup_line_accept
hl_backup_line_bad:
 jmp native_backup_line_reject

hl_backup_parse:
 mov d0,d3
 mov a0,a2
 cmp 14,d3
 bcs hl_backup_unrecognized
 mov hl_backup_prefix,a1
 mov 14,d0
hl_backup_cmp:
 movbu (a2),d1
 movbu (a1),d2
 cmp d1,d2
 bne hl_backup_unrecognized
 inc a2
 inc a1
 add -1,d0
 bne hl_backup_cmp
 mov d3,d0
 add -14,d0
 cmp 96,d0
 bne hl_backup_malformed
 mov hl_backup_state,a0
 mov (4,a0),d0
 cmp 0,d0
 bne hl_backup_malformed
 add 8,a0
 mov 48,d3
hl_backup_decode:
 movbu (a2),d0
 call hl_hex_nibble,[],4
 cmp 16,d0
 bcc hl_backup_ok1
hl_backup_malformed:
 mov hl_backup_state,a0
 mov 2,d0
 mov d0,(4,a0)
 mov 2,d0
 ret [d2,d3,a2,a3],24
hl_backup_ok1:
 asl 4,d0
 mov d0,d1
 inc a2
 movbu (a2),d0
 call hl_hex_nibble,[],4
 cmp 16,d0
 bcc hl_backup_ok2
 bra hl_backup_malformed
hl_backup_ok2:
 or d1,d0
 movbu d0,(a0)
 inc a0
 inc a2
 add -1,d3
 bne hl_backup_decode
 mov hl_backup_state,a0
 mov 1,d0
 mov d0,(4,a0)
 mov 1,d0
 ret [d2,d3,a2,a3],24
hl_backup_unrecognized:
 clr d0
 ret [d2,d3,a2,a3],24

hl_hex_nibble:
 mov d0,d1
 sub 48,d1
 cmp 10,d1
 bcs hl_hex_digit
 mov d0,d1
 sub 65,d1
 cmp 6,d1
 bcs hl_hex_af
 mov d0,d1
 sub 97,d1
 cmp 6,d1
 bcs hl_hex_af_lc
 mov 16,d0
 ret [],4
hl_hex_digit:
 mov d1,d0
 ret [],4
hl_hex_af:
 add 10,d1
 mov d1,d0
 ret [],4
hl_hex_af_lc:
 add 10,d1
 mov d1,d0
 ret [],4

hl_backup_apply:
 mov hl_backup_state,a2
 mov (4,a2),d0
 cmp 1,d0
 bne hl_backup_apply_done
 add 8,a2
 mov 928,d2
 mov 48,d3
hl_backup_apply_loop:
 movbu (a2),d0
 mov d0,d1
 xor 255,d1
 asl 8,d1
 or d1,d0
 or 0x48310000,d0
 mov d0,a0
 mov d2,d0
 mov 1,d1
 call stock_active_set,[d2],8
 inc a2
 inc d2
 add -1,d3
 bne hl_backup_apply_loop
 call hl_publish,[],4
hl_backup_apply_done:
 clr d0
 ret [],4

.section .backup_data,"aw"
.balign 4
hl_backup_state:
 .space 56,0
hl_backup_prefix:
 .ascii "2,OM3_HSL_V1,"
hl_backup_hex:
 .ascii "0123456789ABCDEF"

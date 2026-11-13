/* OM-3 1100: packed H/L via native ACTIVE bank. 4 profiles x 12 sectors.
 * Word format 0x4831CCVV (same contract as PEN-F). IDs 928-975.
 */
.section .hsl_cells,"ax"
.global hl_decode_cell, hl_active_set, hl_active_snapshot

hl_decode_cell:
 mov d0,a0
 lsr 16,d0
 cmp 0x4831,d0
 bne hl_decode_zero
 mov a0,d0
 mov d0,d1
 lsr 8,d1
 xor d0,d1
 and 255,d1
 cmp 255,d1
 bne hl_decode_zero
 mov d0,d1
 asl 28,d1
 asr 28,d1
 cmp -5,d1
 blt hl_decode_zero
 cmp 5,d1
 bgt hl_decode_zero
 mov d0,d1
 asl 24,d1
 asr 28,d1
 cmp -5,d1
 blt hl_decode_zero
 cmp 5,d1
 bgt hl_decode_zero
 and 255,d0
 ret [],4
hl_decode_zero:
 clr d0
 ret [],4

hl_active_set:
 mov d0,d2
 mov d1,d3
 mov a0,a2
 sub 928,d0
 cmp 48,d0
 bcc hl_set_reject
 sub 1,d1
 cmp 2,d1
 bcc hl_set_reject
 mov a2,d0
 cmp -5,d0
 blt hl_set_reject
 cmp 5,d0
 bgt hl_set_reject
 mov d2,d0
 mov 1,d1
 call stock_active_get,[d2],8
 call hl_decode_cell,[],4
 mov a2,d1
 and 15,d1
 cmp 1,d3
 beq hl_set_hue
 and 15,d0
 asl 4,d1
 bra hl_set_merge
hl_set_hue:
 and 240,d0
hl_set_merge:
 or d1,d0
 mov d0,d1
 xor 255,d1
 asl 8,d1
 or d1,d0
 or 0x48310000,d0
 mov d0,a0
 mov d2,d0
 mov 1,d1
 call stock_active_set,[d2],8
 mov 1,d0
 ret [d2,d3,a2],20
hl_set_reject:
 clr d0
 ret [d2,d3,a2],20

/* d0 = profile 1..4, a0 = 12-byte dest. */
hl_active_snapshot:
 mov a0,a2
 sub 1,d0
 cmp 4,d0
 bcc hl_snapshot_zero
 mov d0,d1
 asl 1,d0
 add d1,d0
 asl 2,d0
 add 928,d0
 mov d0,d2
 mov 12,d3
hl_snapshot_loop:
 mov d2,d0
 mov 1,d1
 call stock_active_get,[d2],8
 call hl_decode_cell,[],4
 movbu d0,(a2)
 inc a2
 inc d2
 add -1,d3
 bne hl_snapshot_loop
 ret [d2,d3,a2],20
hl_snapshot_zero:
 mov 12,d3
 clr d0
hl_snapshot_zero_loop:
 movbu d0,(a2)
 inc a2
 add -1,d3
 bne hl_snapshot_zero_loop
 ret [d2,d3,a2],20

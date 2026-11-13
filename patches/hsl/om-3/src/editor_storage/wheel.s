/* Path1 wheel body replaces COLOR2 expand (149B). COLOR1/3/4 are 3-byte jmps.
 * Path2 body replaces path2 COLOR2 expand. Buffers: path1 d2, path2 a3.
 */
.section .wheel_color1_hook,"ax"
 .byte 0xcc
 .short hsl_wheel_p1_c1 - (.-1)
.section .wheel_color3_hook,"ax"
 .byte 0xcc
 .short hsl_wheel_p1_c3 - (.-1)
.section .wheel_color4_hook,"ax"
 .byte 0xcc
 .short hsl_wheel_p1_c4 - (.-1)

.section .hsl_wheel,"ax"
.global hsl_wheel_p1_c1,hsl_wheel_p1_c2,hsl_wheel_p1_c3,hsl_wheel_p1_c4
hsl_wheel_p1_c2:
 mov 940,d0
 bra hsl_wheel_p1
hsl_wheel_p1_c1:
 mov 928,d0
 bra hsl_wheel_p1
hsl_wheel_p1_c3:
 mov 952,d0
 bra hsl_wheel_p1
hsl_wheel_p1_c4:
 mov 964,d0
hsl_wheel_p1:
 mov d2,a1
 mov d0,d2
 mov section_mask,a0
 movbu (a0),d0
 and 4,d0
 beq hsl_wheel_sat1
 mov axis_uncached,a0
 movbu (a0),d1
 sub 1,d1
 cmp 2,d1
 bcc hsl_wheel_sat1
 mov d2,d0
 sub 928,d0
 mov source_uncached,a0
 add d0,a0
 mov 12,d0
p1_loop:
 movbu (a0),d3
 cmp 0,d1
 beq p1_hue
 asl 24,d3
 bra p1_signed
p1_hue:
 asl 28,d3
p1_signed:
 asr 28,d3
 cmp -5,d3
 blt p1_zero
 cmp 5,d3
 ble p1_store
p1_zero:
 clr d3
p1_store:
 movbu d3,(a1)
 inc a0
 inc a1
 add -1,d0
 bne p1_loop
 jmp wheel_resume_p1
hsl_wheel_sat1:
 mov 12,d1
p1_sat:
 mov d2,d0
 call stock_raw_get,[],4
 movbu d0,(a1)
 inc d2
 inc a1
 add -1,d1
 bne p1_sat
 jmp wheel_resume_p1
 .fill 149-(.-hsl_wheel_p1_c2),1,0xcb

.section .wheel2_color1_hook,"ax"
 .byte 0xcc
 .short hsl_wheel_p2_c1 - (.-1)
.section .wheel2_color3_hook,"ax"
 .byte 0xcc
 .short hsl_wheel_p2_c3 - (.-1)
.section .wheel2_else_hook,"ax"
 .byte 0xcc
 .short hsl_wheel_p2_else - (.-1)

.section .hsl_wheel2,"ax"
.global hsl_wheel_p2_c1,hsl_wheel_p2_c2,hsl_wheel_p2_c3,hsl_wheel_p2_else
hsl_wheel_p2_c2:
 mov 940,d0
 bra hsl_wheel_p2
hsl_wheel_p2_c1:
 mov 928,d0
 bra hsl_wheel_p2
hsl_wheel_p2_c3:
 mov 952,d0
 bra hsl_wheel_p2
hsl_wheel_p2_else:
 mov 928,d0
hsl_wheel_p2:
 mov a3,a1
 mov d0,d2
 mov section_mask,a0
 movbu (a0),d0
 and 4,d0
 beq hsl_wheel_sat2
 mov axis_uncached,a0
 movbu (a0),d1
 sub 1,d1
 cmp 2,d1
 bcc hsl_wheel_sat2
 mov d2,d0
 sub 928,d0
 mov source_uncached,a0
 add d0,a0
 mov 12,d0
p2_loop:
 movbu (a0),d3
 cmp 0,d1
 beq p2_hue
 asl 24,d3
 bra p2_signed
p2_hue:
 asl 28,d3
p2_signed:
 asr 28,d3
 cmp -5,d3
 blt p2_zero
 cmp 5,d3
 ble p2_store
p2_zero:
 clr d3
p2_store:
 movbu d3,(a1)
 inc a0
 inc a1
 add -1,d0
 bne p2_loop
 jmp wheel_resume_p2
hsl_wheel_sat2:
 mov 12,d1
p2_sat:
 mov d2,d0
 call stock_raw_get,[],4
 movbu d0,(a1)
 inc d2
 inc a1
 add -1,d1
 bne p2_sat
 jmp wheel_resume_p2
 .fill 149-(.-hsl_wheel_p2_c2),1,0xcb

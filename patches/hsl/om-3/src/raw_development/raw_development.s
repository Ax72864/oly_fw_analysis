/* OM-3 RAW develop: snapshot current profile H/L into owner row. */
.section .raw_acquire_hook,"ax"
 jmp hl_raw_acquire
 nop

.section .raw_acquire,"ax"
.global hl_raw_acquire
hl_raw_acquire:
 movm [d2,d3,a2,a3,other],(sp)
 mov psw,d2
 add -4,sp
 mov d2,(4,sp)
 mov (48,sp),d2
 mov section_mask,a0
 movbu (a0),d0
 and 4,d0
 beq hl_raw_done
 mov a2,a0
 movbu (37689,a0),d0
 cmp 11,d0
 bne hl_raw_neutral
 call hl_source_to_owner,[],4
 bra hl_raw_done
hl_raw_neutral:
 call hl_owner_row,[],4
 cmp 0,a0
 beq hl_raw_done
 clr d0
 .irp offset,0,4,8
 mov d0,(\offset,a0)
 .endr
hl_raw_done:
 mov (4,sp),d2
 add 4,sp
 mov d2,psw
 movm (sp),[d2,d3,a2,a3,other]
 movbu (37689,a2),d0
 jmp raw_acquire_resume

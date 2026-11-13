/* OM-3 1100: publish H/L into live source + ensure section-mask bit2. */
.macro preserve
 movm [d2,d3,a2,a3,other],(sp)
 mov psw,d2
 add -4,sp
 mov d2,(4,sp)
 mov (48,sp),d2
.endm
.macro restore
 mov (4,sp),d2
 add 4,sp
 mov d2,psw
 movm (sp),[d2,d3,a2,a3,other]
.endm

.section .persist_boot_hook,"ax"
 jmp hl_boot_publish

.section .persist_commit_hook,"ax"
 jmp hl_commit_publish
 nop

.section .persist_refresh_hook,"ax"
 jmp hl_refresh_publish

.section .hsl_persist,"ax"
.global hl_publish,hl_boot_publish,hl_commit_publish,hl_refresh_publish
.global hl_refresh_profile,hl_ensure_mask

hl_ensure_mask:
 mov section_mask,a0
 movbu (a0),d0
 or 4,d0
 movbu d0,(a0)
 ret [],0

hl_publish:
 call hl_ensure_mask,[],0
 .irp profile,1,2,3,4
 mov \profile,d0
 mov source_uncached+(\profile-1)*12,a0
 call hl_active_snapshot,[d2,d3,a2],20
 .endr
 ret [],4

hl_boot_publish:
 call stock_boot_reset,[],4
 call hl_publish,[],4
 jmp stock_boot_resume

hl_commit_publish:
 preserve
 call hl_publish,[],4
 restore
 mov a2,d0
 exthu d0
 ret [d2,d3,a2,a3],36

hl_refresh_publish:
 preserve
 cmp 0,d0
 bne hl_refresh_staged
 call hl_publish,[],4
hl_refresh_staged:
 restore
 mov d0,d2
 extbu d2
 mov d2,d0
 mov sp,a0
 inc4 a0
 jmp stock_refresh_resume

hl_refresh_profile:
 cmp 940,d2
 bcs hl_refresh1
 cmp 952,d2
 bcs hl_refresh2
 cmp 964,d2
 bcs hl_refresh3
 jmp stock_color4_refresh
hl_refresh1:
 jmp stock_color1_refresh
hl_refresh2:
 jmp stock_color2_refresh
hl_refresh3:
 jmp stock_color3_refresh

.section .persist_source,"aw"
.global hl_profile_source
hl_profile_source:
 .rept 48
 .byte 0x77
 .endr

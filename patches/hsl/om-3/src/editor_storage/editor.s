/* OM-3 1100 HSL editor: S/H/L for COLOR1-4 (928-975). */
.section .hsl_set_hook,"ax"
 call hsl_set,[d2,d3,a2,a3],68

.section .hsl_get_pointer,"a"
 .long hsl_get
.section .hsl_default_pointer,"a"
 .long hsl_default
.section .hsl_axis,"aw"
 .byte 0

.section .hsl_dispatch_hook,"ax"
 jmp hsl_dispatch

.section .hsl_ui,"ax"
.global hsl_set, hsl_get, hsl_default
.global hl_active_set_impl, hl_publish_impl, hl_refresh_profile_impl

hsl_set:
 mov d0,d2
 sub 928,d2
 cmp 48,d2
 bcc hsl_stock_set
 mov section_mask,a3
 movbu (a3),d3
 and 4,d3
 beq hsl_stock_set
 mov axis_uncached,a3
 movbu (a3),d3
 sub 1,d3
 cmp 2,d3
 bcc hsl_stock_set
 cmp -5,d1
 blt hsl_reject
 cmp 5,d1
 bgt hsl_reject
 mov d1,a0
 mov d3,d1
 inc d1
 mov d2,d0
 add 928,d0
 call hl_active_set,[d2,d3,a2],20
 cmp 1,d0
 bne hsl_reject
 call hl_publish,[],4
 mov d2,d0
 add 928,d0
 mov d0,d2
 call hl_refresh_profile,[],0
 mov 1,d0
 ret [d2,d3,a2,a3],68
hsl_reject:
 clr d0
 ret [d2,d3,a2,a3],68
hsl_stock_set:
 jmp stock_manager

hsl_get:
 mov d0,d1
 exthu d1
 sub 928,d1
 cmp 48,d1
 bcc hsl_stock_get
 cmp 0,a1
 beq hsl_stock_get
 mov section_mask,a0
 movbu (a0),d1
 and 4,d1
 beq hsl_stock_get
 mov axis_uncached,a0
 movbu (a0),d1
 sub 1,d1
 cmp 2,d1
 bcc hsl_stock_get
 exthu d0
 sub 928,d0
 mov source_uncached,a0
 add d0,a0
 movbu (a0),d0
 cmp 0,d1
 beq hsl_get_hue
 asl 24,d0
 bra hsl_get_signed
hsl_get_hue:
 asl 28,d0
hsl_get_signed:
 asr 28,d0
 cmp -5,d0
 blt hsl_get_zero
 cmp 5,d0
 ble hsl_get_store
hsl_get_zero:
 clr d0
hsl_get_store:
 mov d0,(a1)
 clr d0
 retf [],0
hsl_stock_get:
 jmp stock_get

hsl_default:
 mov d0,d1
 exthu d1
 sub 928,d1
 cmp 48,d1
 bcc hsl_stock_default
 mov axis_uncached,a0
 movbu (a0),d1
 sub 1,d1
 cmp 2,d1
 bcc hsl_stock_default
 clr d0
 mov d0,(a1)
 clr d0
 retf [],0
hsl_stock_default:
 jmp stock_default

hsl_dispatch:
 mov (16,sp),d0
 cmp 0x9016,d0
 bne hsl_dispatch_stock
 mov axis_uncached,a0
 movbu (a0),d0
 add 1,d0
 cmp 3,d0
 blt hsl_dispatch_store
 clr d0
hsl_dispatch_store:
 movbu d0,(a0)
hsl_dispatch_stock:
 call stock_fsm_descriptor,[],0
 jmp stock_dispatch_resume

/* Compatibility wrappers used by earlier stubs. */
hl_active_set_impl:
 jmp hl_active_set
hl_publish_impl:
 jmp hl_publish
hl_refresh_profile_impl:
 jmp hl_refresh_profile

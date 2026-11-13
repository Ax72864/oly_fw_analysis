/* OM-3 ORF: after native CMIO header call, inject packed H/L weights. */
.section .native_orf_hook,"ax"
 call cmio_capture_export,[d2,a2],64

.section .native_orf_export,"ax"
.global cmio_capture_export
cmio_capture_export:
 movm [d2,d3,a3],(sp)
 add -16,sp
 mov a0,(4,sp)
 mov (56,sp),a0
 mov a0,(8,sp)
 mov (4,sp),a0
 call native_orf_copy,[d2,a2],64
 exthu d0
 cmp 0,d0
 bne cmio_export_done
 mov (8,sp),a0
 movbu (37689,a0),d1
 cmp 11,d1
 bne cmio_export_done
 movbu (37719,a0),d1
 add -1,d1
 cmp 4,d1
 bcc cmio_export_done
 call hl_owner_row,[],4
 cmp 0,a0
 beq cmio_try_source
 bra cmio_have_row
cmio_try_source:
 mov (8,sp),a0
 movbu (37719,a0),d0
 mov source_uncached,a0
 add -1,d0
 cmp 4,d0
 bcc cmio_export_done
 mov d0,d1
 asl 1,d0
 add d1,d0
 asl 2,d0
 add d0,a0
cmio_have_row:
 mov a0,a1
 mov (8,sp),a0
 add 37694,a0
 mov 12,d2
cmio_copy_packed:
 movbu (a1),d0
 movbu d0,(a0)
 inc a1
 inc a0
 add -1,d2
 bne cmio_copy_packed
 clr d0
cmio_export_done:
 add 16,sp
 movm (sp),[d2,d3,a3]
 exthu d0
 ret [d2,a2],64

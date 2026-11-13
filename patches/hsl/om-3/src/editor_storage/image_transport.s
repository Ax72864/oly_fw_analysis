/* OM-3 snapshot transport. Owner field delta +19094 vs PEN-F.
 * Rows: 32 x 12 packed bytes, index = (owner>>8) & 31.
 */
.macro save_context
 movm [d2,d3,a2,a3,other],(sp)
 mov psw,d2
 add -4,sp
 mov d2,(4,sp)
 mov (48,sp),d2
.endm
.macro restore_context
 mov (4,sp),d2
 add 4,sp
 mov d2,psw
 movm (sp),[d2,d3,a2,a3,other]
.endm

.section .capture_acquire,"ax"
 jmp hl_capture_acquire
 nop

.section .capture_to_job,"ax"
 jmp hl_capture_to_job
 nop

.section .recording_to_job,"ax"
 jmp hl_recording_to_job
 nop

.section .transport,"ax"
.global hl_owner_row, hl_source_to_owner, hl_owner_to_job
.global hl_capture_acquire, hl_capture_to_job, hl_recording_to_job

hl_capture_acquire:
 save_context
 mov (56,sp),a0
 call hl_source_to_owner,[],4
 restore_context
 mov 63401,d0
 jmp capture_acquire_resume


hl_capture_to_job:
 save_context
 mov (56,sp),a0
 mov d3,a2
 add 14920,a2
 call hl_owner_to_job,[],4
 restore_context
 movbu (37718,a0),d0
 jmp capture_job_resume

hl_recording_to_job:
 save_context
 mov (72,sp),a0
 mov d3,a2
 add 14920,a2
 call hl_owner_to_job,[],4
 restore_context
 movbu (37682,a0),d0
 jmp recording_job_resume

hl_source_to_owner:
 mov a0,a3
 call hl_owner_row,[],4
 cmp 0,a0
 beq hl_source_done
 mov a0,a1
 mov a3,a0
 movbu (37719,a0),d0
 mov source_uncached,a0
 add -1,d0
 cmp 4,d0
 bcc hl_source_neutral
 mov d0,d1
 asl 1,d0
 add d1,d0
 asl 2,d0
 add d0,a0
 bra hl_source_copy
hl_source_neutral:
 mov hl_zero_source,a0
hl_source_copy:
 .irp off,0,4,8
 mov (\off,a0),d0
 mov d0,(\off,a1)
 .endr
hl_source_done:
 ret [],4

hl_owner_to_job:
 call hl_owner_row,[],4
 cmp 0,a0
 bne hl_have_owner
 mov hl_zero_source,a0
hl_have_owner:
 mov a2,a1
 mov 12,d2
hl_unpack_loop:
 movbu (a0),d0
 mov d0,d1
 asl 28,d0
 asr 28,d0
 movbu d0,(a1)
 asl 24,d1
 asr 28,d1
 movbu d1,(12,a1)
 inc a0
 inc a1
 add -1,d2
 bne hl_unpack_loop
 ret [],4

hl_owner_row:
 mov a0,d0
 mov d0,d1
 and 0xe0000000,d1
 cmp 0x60000000,d1
 beq hl_alias_ok
 cmp 0xa0000000,d1
 bne hl_no_owner
hl_alias_ok:
 lsr 8,d0
 and 31,d0
 mov d0,d1
 asl 1,d0
 add d1,d0
 asl 2,d0
 mov hl_rows_uncached,a0
 add d0,a0
 ret [],4
hl_no_owner:
 mov 0,a0
 ret [],4

.balign 4
hl_zero_source:
 .space 12,0

.section .transport_rows,"aw"
.global hl_rows
hl_rows:
 .space 384,0

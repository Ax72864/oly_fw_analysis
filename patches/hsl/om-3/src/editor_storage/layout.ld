SECTIONS {
.hsl_set_hook 0x60b8798b : { *(.hsl_set_hook) }
.hsl_get_pointer 0x60e57480 : { *(.hsl_get_pointer) }
.hsl_default_pointer 0x60e57510 : { *(.hsl_default_pointer) }
.hsl_axis 0x6071cf00 : { *(.hsl_axis) }
.hsl_dispatch_hook 0x610f5f9e : { *(.hsl_dispatch_hook) }
.hsl_ui 0x607189a4 : { *(.hsl_ui) }
.wheel_color1_hook 0x60b1d0c7 : { *(.wheel_color1_hook) }
.wheel_color3_hook 0x60b1d219 : { *(.wheel_color3_hook) }
.wheel_color4_hook 0x60b1d2c2 : { *(.wheel_color4_hook) }
.hsl_wheel 0x60b1d170 : { *(.hsl_wheel) }
.wheel2_color1_hook 0x60cce97e : { *(.wheel2_color1_hook) }
.wheel2_color3_hook 0x60cceac8 : { *(.wheel2_color3_hook) }
.wheel2_else_hook 0x60cceb77 : { *(.wheel2_else_hook) }
.hsl_wheel2 0x60ccea23 : { *(.hsl_wheel2) }
.persist_boot_hook 0x603f0301 : { *(.persist_boot_hook) }
.persist_commit_hook 0x60419d4f : { *(.persist_commit_hook) }
.persist_refresh_hook 0x604040ff : { *(.persist_refresh_hook) }
.hsl_cells 0x60718da4 : { *(.hsl_cells) }
.hsl_persist 0x60718f40 : { *(.hsl_persist) }
.persist_source 0x60719e00 : { *(.persist_source) }
.capture_acquire 0x603e7f34 : { *(.capture_acquire) }
.capture_to_job 0x608abbcd : { *(.capture_to_job) }
.recording_to_job 0x6054fd82 : { *(.recording_to_job) }
.transport 0x6071a000 : { *(.transport) }
.transport_rows 0x6071a400 : { *(.transport_rows) }
.raw_acquire_hook 0x618e28ab : { *(.raw_acquire_hook) }
.raw_acquire 0x6071b000 : { *(.raw_acquire) }
.native_orf_hook 0x60550363 : { *(.native_orf_hook) }
.native_orf_export 0x6071b100 : { *(.native_orf_export) }
}
axis_uncached = 0xa071cf00;
source_uncached = 0xa0719e00;
stock_manager = 0x60bb528f;
stock_get = 0x6031fa67;
stock_default = 0x60b86e44;
stock_fsm_descriptor = 0x610f6102;
stock_dispatch_resume = 0x610f5fa3;
section_mask = 0xa3371164;
stock_active_get = 0x604197e2;
stock_active_set = 0x6041980b;
stock_boot_reset = 0x603f0fb6;
stock_boot_resume = 0x603f0306;
stock_refresh_resume = 0x60404104;
stock_color1_refresh = 0x60400fc0;
stock_color2_refresh = 0x60400fdb;
stock_color3_refresh = 0x60400ff6;
stock_color4_refresh = 0x60401011;
stock_raw_get = 0x603f039d;
wheel_resume_p1 = 0x60b1d363;
wheel_resume_p2 = 0x60cced2b;
capture_acquire_resume = 0x603e7f3a;
capture_job_resume = 0x608abbd3;
recording_job_resume = 0x6054fd88;
hl_rows_uncached = 0xa071a400;
raw_acquire_resume = 0x618e28b1;
native_orf_copy = 0x604b0d0b;

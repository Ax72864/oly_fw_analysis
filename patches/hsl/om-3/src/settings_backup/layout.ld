SECTIONS {
.backup_export_hook 0x619fd0f8 : { *(.backup_export_hook) }
.backup_header_hook 0x619fd7e1 : { *(.backup_header_hook) }
.backup_line_hook 0x619fd859 : { *(.backup_line_hook) }
.backup_footer_hook 0x619fd8f2 : { *(.backup_footer_hook) }
.backup_export 0x619f5108 : { *(.backup_export) }
.backup_lifecycle 0x619f5300 : { *(.backup_lifecycle) }
.backup_import 0x619f5380 : { *(.backup_import) }
.backup_data 0x619f5700 : { *(.backup_data) }
}
hl_decode_cell = 0x60718da4;
hl_publish = 0x60718f50;
stock_active_get = 0x604197e2;
stock_active_set = 0x6041980b;
native_backup_write3 = 0x619fd0fc;
native_backup_export_fail = 0x619fd10b;
native_backup_header_resume = 0x619fd7e7;
native_backup_line_resume = 0x619fd85f;
native_backup_line_accept = 0x619fd8a9;
native_backup_line_reject = 0x619fd879;
native_backup_footer_resume = 0x619fd8f9;

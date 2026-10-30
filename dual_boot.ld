SECTIONS {
    . = 0x40081000;
    .text : {
        *(.literal .literal.*)
        KEEP(*(.text.entry))
        *(.text .text.*)
    }

    .rodata 0x3fff1400 : {
        __dual_boot_data_start = .;
        *(.rodata .rodata.*)
        *(.data .data.*)
        . = ALIGN(4);
        __dual_boot_data_end = .;
    }
}

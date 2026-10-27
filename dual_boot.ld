SECTIONS {
    . = 0x40081000;
    .text : {
        *(.literal .literal.*)
        KEEP(*(.text.entry))
        *(.text .text.*)
        *(.rodata .rodata.*)
    }
}

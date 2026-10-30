#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#include "soc/io_mux_reg.h"
#include "soc/gpio_reg.h"
#include "soc/gpio_periph.h"
#include "font5x7.h"

// ROM functions
extern void esp_rom_delay_us(uint32_t us);
extern int ets_printf(const char *fmt, ...);

// Bootloader functions
extern int bootloader_utility_get_selected_boot_partition(const void *bs);

// OLED SH1106 Pin definitions (from MIDI Goblin schematic / code)
#define OLED_SDA    21
#define OLED_CLK    22
#define OLED_DC     17
#define OLED_CS     5
#define OLED_RESET  4

// Multiplexer Pin definitions
#define MUX_S0      27
#define MUX_S1      14
#define MUX_S2      13
#define MUX_S3      12
#define MUX_SIG     34

// Rotary Encoder Pins
#define ENC_A       39
#define ENC_B       36

// DevKit BOOT button
#define BOOT_BTN_PIN 0

// UART0 hardware registers for non-blocking serial input
#define UART0_FIFO_REG   (*(volatile uint32_t *)0x3FF40000)
#define UART0_STATUS_REG (*(volatile uint32_t *)0x3FF4001C)

// SH1106 Initialization Sequence
static const uint8_t sh1106_init_seq[] = {
    0xAE,             // Display OFF
    0xD5, 0x80,       // Set Display Clock Divide Ratio / Osc Freq
    0xA8, 0x3F,       // Set Multiplex Ratio (64)
    0xD3, 0x00,       // Set Display Offset (0)
    0x40,             // Set Display Start Line (0)
    0xAD, 0x8B,       // Set DC-DC Pump Enable (8B = internal pump ON)
    0xA1,             // Set Segment Re-Map (col 127 mapped to SEG0)
    0xC8,             // Set COM Output Scan Direction (remapped)
    0xDA, 0x12,       // Set COM Pins Hardware Configuration
    0x81, 0xFF,       // Set Contrast (255 max brightness)
    0xD9, 0x1F,       // Set Pre-charge Period
    0xDB, 0x40,       // Set VCOMH Deselect Level
    0x33,             // Set VPP (9V)
    0xA6,             // Set Normal Display (non-inverted)
    0x20, 0x10,       // Set Page Addressing Mode
    0xA4,             // Entire Display ON (Resume to RAM content)
    0xAF              // Display ON
};

// Framebuffer at fixed internal DRAM address (1024 bytes)
// Safe region between bootloader data (ends at 0x3fff04d0) and stack (starts at 0x3ffff000)
#define fb ((uint8_t (*)[128])0x3fff1000)

static void init_hardware_pins(void) {
    // OLED pins
    PIN_FUNC_SELECT(IO_MUX_GPIO4_REG, FUNC_GPIO4_GPIO4);
    PIN_FUNC_SELECT(IO_MUX_GPIO5_REG, FUNC_GPIO5_GPIO5);
    PIN_FUNC_SELECT(IO_MUX_GPIO17_REG, FUNC_GPIO17_GPIO17);
    PIN_FUNC_SELECT(IO_MUX_GPIO21_REG, FUNC_GPIO21_GPIO21);
    PIN_FUNC_SELECT(IO_MUX_GPIO22_REG, FUNC_GPIO22_GPIO22);

    // MUX select pins
    PIN_FUNC_SELECT(IO_MUX_GPIO27_REG, FUNC_GPIO27_GPIO27);
    PIN_FUNC_SELECT(IO_MUX_GPIO12_REG, FUNC_MTDI_GPIO12);
    PIN_FUNC_SELECT(IO_MUX_GPIO13_REG, FUNC_MTCK_GPIO13);
    PIN_FUNC_SELECT(IO_MUX_GPIO14_REG, FUNC_MTMS_GPIO14);

    // Input pins
    PIN_FUNC_SELECT(IO_MUX_GPIO0_REG, FUNC_GPIO0_GPIO0);
    PIN_INPUT_ENABLE(IO_MUX_GPIO0_REG);
    PIN_FUNC_SELECT(IO_MUX_GPIO34_REG, FUNC_GPIO34_GPIO34);
    PIN_INPUT_ENABLE(IO_MUX_GPIO34_REG);
    PIN_FUNC_SELECT(IO_MUX_GPIO36_REG, FUNC_GPIO36_GPIO36);
    PIN_INPUT_ENABLE(IO_MUX_GPIO36_REG);
    PIN_FUNC_SELECT(IO_MUX_GPIO39_REG, FUNC_GPIO39_GPIO39);
    PIN_INPUT_ENABLE(IO_MUX_GPIO39_REG);

    // Output enable
    uint32_t out_mask = (1 << OLED_RESET) | (1 << OLED_CS) | (1 << OLED_DC) |
                        (1 << OLED_SDA) | (1 << OLED_CLK) |
                        (1 << MUX_S0) | (1 << MUX_S1) | (1 << MUX_S2) | (1 << MUX_S3);
    GPIO.enable_w1ts = out_mask;
}

static inline void oled_spi_byte(uint8_t byte) {
    for (int i = 7; i >= 0; i--) {
        if ((byte >> i) & 1) {
            GPIO.out_w1ts = (1 << OLED_SDA);
        } else {
            GPIO.out_w1tc = (1 << OLED_SDA);
        }
        GPIO.out_w1ts = (1 << OLED_CLK);
        for (volatile int d = 0; d < 4; d++);
        GPIO.out_w1tc = (1 << OLED_CLK);
    }
}

static void oled_cmd(uint8_t cmd) {
    GPIO.out_w1tc = (1 << OLED_DC);
    GPIO.out_w1tc = (1 << OLED_CS);
    oled_spi_byte(cmd);
    GPIO.out_w1ts = (1 << OLED_CS);
}

static void oled_init(void) {
    GPIO.out_w1ts = (1 << OLED_CS);
    GPIO.out_w1tc = (1 << OLED_RESET);
    esp_rom_delay_us(10000); // 10ms
    GPIO.out_w1ts = (1 << OLED_RESET);
    esp_rom_delay_us(10000); // 10ms

    for (size_t i = 0; i < sizeof(sh1106_init_seq); i++) {
        oled_cmd(sh1106_init_seq[i]);
    }
}

static void oled_flush(void) {
    for (uint8_t page = 0; page < 8; page++) {
        oled_cmd(0xB0 + page); // Page address
        oled_cmd(0x02);        // Lower col address (2 for SH1106)
        oled_cmd(0x10);        // Higher col address (0)

        GPIO.out_w1ts = (1 << OLED_DC);
        GPIO.out_w1tc = (1 << OLED_CS);
        for (int col = 0; col < 128; col++) {
            oled_spi_byte(fb[page][col]);
        }
        GPIO.out_w1ts = (1 << OLED_CS);
    }
}

static void draw_text(uint8_t page, uint8_t col, const char *str, bool invert) {
    while (*str && col < 124) {
        char c = *str++;
        if (c < 32 || c > 127) c = ' ';
        const uint8_t *glyph = font5x7[c - 32];
        for (int i = 0; i < 5; i++) {
            uint8_t b = glyph[i];
            fb[page][col++] = invert ? ~b : b;
        }
        fb[page][col++] = invert ? 0xFF : 0x00;
    }
}

static void clear_page(uint8_t page) {
    memset(fb[page], 0, 128);
}

static bool read_mux_channel(uint8_t ch) {
    if (ch & 1) GPIO.out_w1ts = (1 << MUX_S0); else GPIO.out_w1tc = (1 << MUX_S0);
    if (ch & 2) GPIO.out_w1ts = (1 << MUX_S1); else GPIO.out_w1tc = (1 << MUX_S1);
    if (ch & 4) GPIO.out_w1ts = (1 << MUX_S2); else GPIO.out_w1tc = (1 << MUX_S2);
    if (ch & 8) GPIO.out_w1ts = (1 << MUX_S3); else GPIO.out_w1tc = (1 << MUX_S3);
    esp_rom_delay_us(10);
    return (GPIO.in1.val & (1 << (MUX_SIG - 32))) != 0;
}

static bool is_boot_btn_pressed(void) {
    return !(GPIO.in & (1 << BOOT_BTN_PIN));
}

// Check non-blocking UART0 input
static int uart_rx_char(void) {
    uint32_t status = UART0_STATUS_REG;
    if ((status & 0xFF) > 0) { // RX FIFO count > 0
        return (int)(UART0_FIFO_REG & 0xFF);
    }
    return -1;
}

// Render the menu UI on OLED and Serial
static void render_menu(int selected, int seconds_left) {
    // Header
    draw_text(0, 4,  " MIDI GOBLIN DUAL   ", false);
    draw_text(1, 0,  "--------------------", false);

    // Option 0: MIDI Goblin
    if (selected == 0) {
        draw_text(3, 2, "> 1. MIDI Goblin   ", true);
    } else {
        draw_text(3, 2, "  1. MIDI Goblin   ", false);
    }

    // Option 1: Pingler
    if (selected == 1) {
        draw_text(4, 2, "> 2. Pingler       ", true);
    } else {
        draw_text(4, 2, "  2. Pingler       ", false);
    }

    // Separator
    draw_text(6, 0,  "--------------------", false);

    // Countdown / instructions
    char countdown_str[24];
    if (seconds_left > 0) {
        countdown_str[0] = 'B'; countdown_str[1] = 'o'; countdown_str[2] = 'o';
        countdown_str[3] = 't'; countdown_str[4] = 'i'; countdown_str[5] = 'n';
        countdown_str[6] = 'g'; countdown_str[7] = ' '; countdown_str[8] = 'i';
        countdown_str[9] = 'n'; countdown_str[10] = ' ';
        countdown_str[11] = '0' + seconds_left;
        countdown_str[12] = 's'; countdown_str[13] = '.'; countdown_str[14] = '.';
        countdown_str[15] = ' '; countdown_str[16] = '('; countdown_str[17] = 'E';
        countdown_str[18] = 'N'; countdown_str[19] = 'C'; countdown_str[20] = ')';
        countdown_str[21] = '\0';
    } else {
        strcpy(countdown_str, "Booting...          ");
    }
    clear_page(7);
    draw_text(7, 2, countdown_str, false);

    oled_flush();
}

// Entry point called from call_start_cpu0 at 0x40080623
int __attribute__((section(".text.entry"))) select_firmware(const void *bs) {
    init_hardware_pins();

    ets_printf("\n\n");
    ets_printf("===================================================\n");
    ets_printf("    MIDI Goblin Dual Bootloader (v1.0)\n");
    ets_printf("===================================================\n");
    ets_printf(" Select:\n");
    ets_printf("   [1] MIDI Goblin (Default)\n");
    ets_printf("   [2] Pingler\n");
    ets_printf(" Controls:\n");
    ets_printf("   - Hardware: Rotary Encoder, MUX buttons, BOOT btn\n");
    ets_printf("   - Serial/QEMU: Press '1' (MIDI Goblin) or '2' (Pingler)\n");
    ets_printf("===================================================\n");

    // Fast-boot check:
    // If Encoder button (ch 15), User 1 (ch 12), or Right (ch 3) is held at power-on:
    bool enc_btn   = read_mux_channel(15);
    bool user1_btn = read_mux_channel(12);
    bool user2_btn = read_mux_channel(13);
    bool left_btn  = read_mux_channel(0);
    bool right_btn = read_mux_channel(3);

    if (enc_btn || user1_btn || right_btn) {
        ets_printf(" [FAST-BOOT] Hardware button held -> Booting Pingler (Slot 1)!\n");
        return 1;
    }
    if (left_btn || user2_btn) {
        ets_printf(" [FAST-BOOT] Hardware button held -> Booting MIDI Goblin (Slot 0)!\n");
        return 0;
    }

    // Normal launch: initialize OLED display
    memset((void *)0x3fff1000, 0, 1024);
    oled_init();

    int selected = 0; // Default to MIDI Goblin (slot 0)
    int seconds_left = 3;
    render_menu(selected, seconds_left);
    ets_printf(" Auto-booting [%s] in %d seconds...\n", selected == 0 ? "MIDI Goblin" : "Pingler", seconds_left);

    // Initial state of encoder
    uint8_t prev_enc_a = (GPIO.in1.val >> (ENC_A - 32)) & 1;
    bool prev_btn_state = false;

    // Countdown loop: 3 seconds (150 iterations * 20ms)
    for (int t = 0; t < 150; t++) {
        esp_rom_delay_us(20000); // 20ms

        // Check serial input (QEMU / Serial terminal keyboard)
        int rx = uart_rx_char();
        if (rx != -1) {
            if (rx == '1' || rx == 'm' || rx == 'M') {
                selected = 0;
                ets_printf(" [SERIAL] Key '%c' pressed -> MIDI Goblin selected!\n", (char)rx);
                break;
            } else if (rx == '2' || rx == 'p' || rx == 'P') {
                selected = 1;
                ets_printf(" [SERIAL] Key '%c' pressed -> Pingler selected!\n", (char)rx);
                break;
            } else if (rx == '\r' || rx == '\n' || rx == ' ') {
                ets_printf(" [SERIAL] Key confirm -> Booting selected!\n");
                break;
            } else if (rx == 'w' || rx == 'k') {
                selected = 0;
                render_menu(selected, seconds_left);
                ets_printf(" [SERIAL] Up -> MIDI Goblin\n");
            } else if (rx == 's' || rx == 'j') {
                selected = 1;
                render_menu(selected, seconds_left);
                ets_printf(" [SERIAL] Down -> Pingler\n");
            }
        }

        // Check if countdown second ticked
        if ((t % 50) == 0 && t > 0) {
            seconds_left--;
            render_menu(selected, seconds_left);
            ets_printf(" Booting [%s] in %d seconds...\n", selected == 0 ? "MIDI Goblin" : "Pingler", seconds_left);
        }

        // Read encoder rotation
        uint8_t cur_enc_a = (GPIO.in1.val >> (ENC_A - 32)) & 1;
        uint8_t cur_enc_b = (GPIO.in1.val >> (ENC_B - 32)) & 1;
        if (cur_enc_a != prev_enc_a && cur_enc_a == 1) { // Rising edge
            if (cur_enc_b == 0) {
                selected = (selected == 0) ? 1 : 0;
            } else {
                selected = (selected == 1) ? 0 : 1;
            }
            render_menu(selected, seconds_left);
            ets_printf(" Selection changed to: %s\n", selected == 0 ? "MIDI Goblin" : "Pingler");
        }
        prev_enc_a = cur_enc_a;

        // Read navigation buttons from MUX
        bool up_pressed    = read_mux_channel(1);
        bool down_pressed  = read_mux_channel(2);
        bool left_pressed  = read_mux_channel(0);
        bool right_pressed = read_mux_channel(3);
        if (up_pressed || left_pressed) {
            if (selected != 0) {
                selected = 0;
                render_menu(selected, seconds_left);
                ets_printf(" Selection changed to: MIDI Goblin\n");
            }
        }
        if (down_pressed || right_pressed) {
            if (selected != 1) {
                selected = 1;
                render_menu(selected, seconds_left);
                ets_printf(" Selection changed to: Pingler\n");
            }
        }

        // Check confirmation button (Encoder Click, Menu, Yes button)
        bool btn_now = read_mux_channel(15) || read_mux_channel(10) || read_mux_channel(9);
        if (btn_now && !prev_btn_state) {
            ets_printf(" Confirmation button clicked!\n");
            break;
        }
        prev_btn_state = btn_now;
    }

    // Show final boot status on OLED
    clear_page(7);
    if (selected == 0) {
        draw_text(7, 2, "Booting MIDI Goblin...", true);
        ets_printf(" >>> Launching MIDI Goblin (slot 0 @ 0x10000)...\n\n");
    } else {
        draw_text(7, 2, "Booting Pingler...    ", true);
        ets_printf(" >>> Launching Pingler (slot 1 @ 0x150000)...\n\n");
    }
    oled_flush();
    esp_rom_delay_us(150000); // 150ms for display visibility

    return selected;
}

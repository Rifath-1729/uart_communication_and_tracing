#ifndef UART_H
#define UART_H

#include "main.h"
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>




void serial_print(const char *format, ...);

void read_serial(char *tmp, char terminator, uint16_t timeout);

int uart_baud_rate_supported(uint32_t baud_rate);
HAL_StatusTypeDef uart_set_baud_rate(uint32_t baud_rate);

void echo_single_byte(uint8_t ch);

#endif

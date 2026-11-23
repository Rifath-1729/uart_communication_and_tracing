#ifndef UART_COMM_2_H
#define UART_COMM_2_H

#include "main.h"

extern UART_HandleTypeDef huart1; // tx trace
extern UART_HandleTypeDef huart2; // print
extern UART_HandleTypeDef huart3; // rx trace

void uart_comm_2_init(void);
void uart_comm_2_process(void);

#endif

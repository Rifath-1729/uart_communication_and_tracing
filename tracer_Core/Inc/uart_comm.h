#ifndef UART_READ_H
#define UART_READ_H

#include "main.h"

extern UART_HandleTypeDef huart1; // L476 DEV A receiver: USART1_RX on PA10(D2) for 232 tx
extern UART_HandleTypeDef huart2; // Output: USART2_TX on PA2(to PC)
extern UART_HandleTypeDef huart3; // L476 DEV B receiver: USART3_RX on PC5 for 232 rx

void uart_receive_rx_channel(UART_HandleTypeDef *huart);
void uart_receive_tx_channel(UART_HandleTypeDef *huart);

void uart_transmit_rx_channel(UART_HandleTypeDef *huart);
void uart_transmit_tx_channel(UART_HandleTypeDef *huart);

#endif

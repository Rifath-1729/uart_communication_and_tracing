#include "uart.h"

extern UART_HandleTypeDef huart1;

#define BUFFER 250

uint16_t tracker = 0;
char rcv_data[BUFFER] = "";


void serial_print(const char *format, ...)
{
	// Format a response line and send it to the PC over USART1.
	char data[250] = " ";

	va_list arglist;
	va_start(arglist, format);

	int len = vsnprintf(data, sizeof(data), format, arglist);

	va_end(arglist);

	if(len < 0){
		return;
	}

	HAL_UART_Transmit(&huart1, (uint8_t *)data, len, 100);
	//HAL_UART_Transmit(&hcom_uart[COM1], (uint8_t *)data, len, 100);
}


void read_serial(char *tmp, char terminator, uint16_t timeout)
{
	// Collect bytes until the terminator, timeout, or buffer limit; discard CR for CRLF input.
	uint16_t count = 0;
	uint32_t start_tick = HAL_GetTick();


	if(tmp == NULL){
		return;
	}

	tmp[0] = '\0';

	while(count < BUFFER-1){
		uint32_t elapsed = HAL_GetTick() - start_tick;
		uint8_t byte;

		if(elapsed >= timeout){
			break;
		}

		if(HAL_UART_Receive(&huart1, &byte, 1, (uint32_t)timeout-elapsed) != HAL_OK){
			break;
		}

		if(byte == (uint8_t)terminator){
			break;
		}

		if(byte == '\r'){
			continue;
		}

		tmp[count++] = (char)byte;
		tmp[count] = '\0';
	}
}

int uart_baud_rate_supported(uint32_t baud_rate)
{
	// Keep the accepted rates aligned with the options offered by the PC tool.
	switch(baud_rate){
		case 9600:
		case 19200:
		case 38400:
		case 57600:
		case 115200:
			return 1;
		default:
			return 0;
	}
}

HAL_StatusTypeDef uart_set_baud_rate(uint32_t baud_rate)
{
	// Reinitialize USART1 at the new rate and restore its FIFO settings.
	if(!uart_baud_rate_supported(baud_rate)){
		return HAL_ERROR;
	}

	huart1.Init.BaudRate = baud_rate;

	if(HAL_UART_Init(&huart1) != HAL_OK){
		return HAL_ERROR;
	}

	if(HAL_UARTEx_SetTxFifoThreshold(&huart1, UART_TXFIFO_THRESHOLD_1_8) != HAL_OK){
		return HAL_ERROR;
	}

	if(HAL_UARTEx_SetRxFifoThreshold(&huart1, UART_RXFIFO_THRESHOLD_1_8) != HAL_OK){
		return HAL_ERROR;
	}

	return HAL_UARTEx_DisableFifoMode(&huart1);
}
void echo_single_byte(uint8_t ch)
{

	if (HAL_UART_Receive(&huart1, &ch, 1, HAL_MAX_DELAY) == HAL_OK)
	{
		HAL_UART_Transmit(&huart1, &ch, 1, 1000);
	}

}




















#include "uart_comm_2.h"
#include <stdio.h>
#include <stdbool.h>
#include <stdarg.h>

#define RX_BUFFER_SIZE 256

static uint8_t usart2_rx_byte;
static uint8_t usart1_rx_byte;
static uint8_t usart3_rx_byte;

static volatile char requested_baud_code;
static uint32_t current_baud = 9600;




typedef struct{
	uint8_t data[RX_BUFFER_SIZE];
	volatile uint16_t head;
	volatile uint16_t tail;
	volatile uint32_t dropped;
} Byte_queue;

// Separate ring buffers keep the two captured UART directions independent.
static Byte_queue devA_queue = {0};
static Byte_queue devB_queue = {0};

static void process_baud_command(void);

// For easy serial print command.
void serial_print(const char *format, ...)
{
	// Format status text and send it to the PC-facing USART2 console.
	char data[250] = " ";

	va_list arglist;
	va_start(arglist, format);
	int len = vsnprintf(data, sizeof(data), format, arglist);
	va_end(arglist);

	if(len < 0){
		return;
	}

	HAL_UART_Transmit(&huart2, (uint8_t *) data, len, 100);
}

static void queue_push(Byte_queue *queue, uint8_t byte)
{
	// Save each received byte for the main loop; count it if this channel's queue is full.
	uint16_t next = (queue->head + 1U) % RX_BUFFER_SIZE;

	if(next == queue->tail){
		queue->dropped++;
		return;
	}

	queue->data[queue->head] = byte;
	queue->head = next;
}

static bool queue_pop(Byte_queue *queue, uint8_t *byte){

	if(queue->tail == queue->head){
		return false;
	}

	*byte = queue->data[queue->tail];
	queue->tail = (queue->tail + 1U) % RX_BUFFER_SIZE;
	return true;
}

static void print_byte(const char *device_name, uint8_t byte)
{
	// Display each byte as hex plus a character when printable, preserving non-text data.
	char line[64];
	int length;

	serial_print("Baud Rate: %lu  ", current_baud);
	if(byte >= 32U && byte <= 126U && byte != '\'' && byte != '\\'){
		length = snprintf(line, sizeof(line), "%s | 0x%02X | '%c'\r\n", device_name, (unsigned int)byte, (char)byte);
	}
	else{
		length = snprintf(line, sizeof(line), "%s | 0x%02X | <non-printable>\r\n", device_name, (unsigned int) byte);

	}

	if(length > 0 && length < (int)sizeof(line)){
		HAL_UART_Transmit(&huart2, (uint8_t *)line, (uint16_t)length, 100);
	}
}

void uart_comm_2_init()
{
	// Start one-byte interrupt receives on both trace inputs and the console baud selector.
	HAL_UART_Receive_IT(&huart1, &usart1_rx_byte, 1); // this one for ft232rl tx
	HAL_UART_Receive_IT(&huart3, &usart3_rx_byte, 1); // this one for ft232rl rx
	HAL_UART_Receive_IT(&huart2, &usart2_rx_byte, 1); // this one for baud set.
}


void uart_comm_2_process()
{
	// Apply any baud request, then drain each direction's queue to the serial monitor.
	uint8_t byte;

	process_baud_command();

	while(queue_pop(&devA_queue, &byte)){
		print_byte("Device A", byte);
	}

	while(queue_pop(&devB_queue, &byte)){
		print_byte("Device B", byte);
	}
}

static void process_baud_command()
{
	// Map console keys 1-5 to a supported capture rate and reconfigure both input UARTs.
	char code = requested_baud_code;
	uint32_t baud = 0;

	if(code == 0){
		return;
	}

	requested_baud_code = 0;

	switch(code){
		case '1':
			baud = 9600;
			break;

		case '2':
			baud = 19200;
			break;

		case '3':
			baud = 38400;
			break;

		case '4':
			baud = 57600;
			break;

		case '5':
			baud = 115200;
			break;

		default:
			return;
	}

	if(baud == current_baud){
		return;
	}

	HAL_UART_AbortReceive(&huart1);
	HAL_UART_AbortReceive(&huart3);

	huart1.Init.BaudRate = baud;
	huart3.Init.BaudRate = baud;

	HAL_StatusTypeDef status1 = HAL_UART_Init(&huart1);
	HAL_StatusTypeDef status3 = HAL_UART_Init(&huart3);

	if(status1 == HAL_OK && status3 == HAL_OK){
		HAL_UART_Receive_IT(&huart1, &usart1_rx_byte, 1);
		HAL_UART_Receive_IT(&huart3, &usart3_rx_byte, 1);

		current_baud = baud;

		char baud_change_ok[100] = "Baud changed\r\n";
		HAL_UART_Transmit(&huart2, (uint8_t *) baud_change_ok, sizeof(baud_change_ok)-1, 100);
	}
	else{
		char baud_change_fail[100] = "Baud change failed\r\n";


		HAL_UART_Transmit(&huart2, (uint8_t *)baud_change_fail, sizeof(baud_change_fail)-1, 100);

	}
}

// BAUD Set Section

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
	// USART2 records baud-selection keys; USART1/3 queue trace bytes and immediately re-arm RX.

	if(huart->Instance == USART2){
		if(usart2_rx_byte >= '1' && usart2_rx_byte <= '5'){
			requested_baud_code = (char)usart2_rx_byte;
		}
		HAL_UART_Receive_IT(huart, &usart2_rx_byte, 1);
		return;
	}
	if(huart->Instance == USART1){
		queue_push(&devA_queue, usart1_rx_byte);
		HAL_UART_Receive_IT(huart, &usart1_rx_byte, 1);
	}
	else if(huart->Instance == USART3){
		queue_push(&devB_queue, usart3_rx_byte);
		HAL_UART_Receive_IT(huart, &usart3_rx_byte, 1);
	}
}

















#include <uart_comm.h>



#define RX_BUFFER_SIZE 256
#define TX_BUFFER_SIZE 256

static uint8_t rx_byte, tx_byte;
static uint8_t rx_buffer[RX_BUFFER_SIZE];
static uint8_t tx_buffer[TX_BUFFER_SIZE];

static volatile uint16_t rx_head = 0, tx_head = 0;
static volatile uint16_t rx_tail = 0, tx_tail = 0;
static volatile uint32_t rx_dropped = 0, tx_dropped = 0;

void uart_receive_rx_channel(UART_HandleTypeDef *huart) // uart3
{
	HAL_UART_Receive_IT(huart, &rx_byte, 1);
}

void uart_receive_tx_channel(UART_HandleTypeDef *huart) //uart1
{
	HAL_UART_Receive_IT(huart, &tx_byte, 1);

}

void uart_transmit_rx_channel(UART_HandleTypeDef *huart) // huart2
{

	if(rx_tail != rx_head){ // // Only print it if there is something to show in the buffer
		char str_A[] = "Device A data: ";
		HAL_UART_Transmit(huart, (uint8_t *)str_A, sizeof(str_A)-1, 100);
	}


	while(rx_tail != rx_head){
		uint8_t byte = rx_buffer[rx_tail];
		rx_tail = (rx_tail+1)% RX_BUFFER_SIZE;

		HAL_UART_Transmit(huart, &byte, 1, 100);
	}

}

void uart_transmit_tx_channel(UART_HandleTypeDef *huart)
{
	if(tx_tail != tx_head){ // Only print it if there is something to show in the buffer
		char str_B[] = "Device B data: ";
		HAL_UART_Transmit(huart, (uint8_t *)str_B, sizeof(str_B)-1, 100);
	}


	while(tx_tail != tx_head){
		uint8_t byte = tx_buffer[tx_tail];
		tx_tail = (tx_tail+1) % TX_BUFFER_SIZE;

		HAL_UART_Transmit(huart, &byte, 1, 100);
	}

}

/*
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart){

	if(huart->Instance == USART1){  // for tx of comm link
		uint16_t next_tx = (tx_head+1) % TX_BUFFER_SIZE;

		if(next_tx != tx_tail){
			tx_buffer[tx_head] = tx_byte;
			tx_head = next_tx;
		}
		else{
			tx_dropped++; // buffer full hence byte is dropped.
		}

		HAL_UART_Receive_IT(&huart1, &tx_byte, 1);
	}

	if(huart->Instance == USART3){
		uint16_t next_rx = (rx_head+1) % RX_BUFFER_SIZE;

		if(next_rx != rx_tail){
			rx_buffer[rx_head] = rx_byte;
			rx_head = next_rx;
		}
		else{
			rx_dropped++;
		}

		HAL_UART_Receive_IT(&huart3, &rx_byte, 1);
	}
}

*/

























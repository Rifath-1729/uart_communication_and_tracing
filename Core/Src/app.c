#include "app.h"

char s_read[250];

void setup()
{
	//
}

void loop()
{
	// Read one PC frame, split its sequence/command/payload, then dispatch the request.
	char *sequence;
	char *command;
	char *payload;
	char *comma1;
	char *comma2;
	char *end;
	unsigned long requested_baud;

	memset(s_read, '\0', sizeof(s_read));
	read_serial(s_read, '\n', 1500);

	if(s_read[0] == '\0'){
		return;
	}

	/*
	* PC → STM32: CMD,0001,MSG,Hello Nucleo\n
	* STM32 → PC: ACK,0001,OK,Hello Nucleoreceived\n
	* CMD,0000,SET_BAUD,<rate>\n
	* ACK,0000,OK,BAUD,<rate>\n
	*/

	if(strncmp(s_read, "CMD,", 4) != 0){
		return;
	}

	sequence = s_read + 4;
	comma1 = strchr(sequence, ',');

	if(comma1 == NULL){
		return;
	}
	*comma1 = '\0';



	command = comma1+1;
	comma2 = strchr(command, ',');

	if(comma2 == NULL){
		serial_print("NACK, %s, BAD_FRAME, Missing payload separator\n", sequence);
		return;
	}
	*comma2 = '\0';
	payload = comma2 + 1;

	if(strcmp(command, "SET_BAUD") == 0){
		requested_baud = strtoul(payload, &end, 10);

		if(end == payload || *end != '\0' || requested_baud > 115200UL || !uart_baud_rate_supported((uint32_t)requested_baud)){
			serial_print("NACK,%s,BAD_BAUD,Unsupported baud rate\n", sequence);
			return;
		}

		// Acknowledge at the old rate so the PC can receive the reply before switching too.

		serial_print("ACK,%s,OK,BAUD,%lu\n", sequence, requested_baud);
		HAL_Delay(20);

		if(uart_set_baud_rate((uint32_t)requested_baud) != HAL_OK){
			Error_Handler();
		}
		return;
	}

	if(strcmp(command, "MSG") == 0){
		// Confirm message delivery by returning the payload in an ACK.
		serial_print("ACK,%s,OK,%sreceived\n", sequence, payload);
		return;
	}

	if(strcmp(command, "PING") == 0){
		// Provide a short response for checking that the UART link is alive.
		serial_print("ACK,%s,OK,PONG\n", sequence);
		return;
	}

	serial_print("NACK,%s,UNKNOWN_CMD,Unsupported command\n", sequence);


}


















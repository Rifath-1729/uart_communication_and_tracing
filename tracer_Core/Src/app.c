#include "app.h"
#include "uart_comm_2.h"


void setup()
{

	uart_comm_2_init();
}

void loop()
{

	uart_comm_2_process();

}

















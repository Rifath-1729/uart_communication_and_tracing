"""Send a message to an STM32 board once per second and display its replies."""

from __future__ import annotations

import threading
import time
import re
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    raise SystemExit(
        "pyserial is required. Install it with:\n"
        "    py -m pip install pyserial"
    )


SEND_INTERVAL_SECONDS = 1.0
SERIAL_READ_TIMEOUT_SECONDS = 0.005
MAX_PAYLOAD_BYTES = 200
COMMANDS_PER_BATCH = 5
BAUD_RATES = (9600, 19200, 38400, 57600, 115200)


class SerialTool:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("USART1 General Command / ACK Tool")
        self.root.minsize(740, 610)

        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.closing = False

        self.port_var = tk.StringVar()
        self.current_baud_var = tk.StringVar(value="9600")
        self.baud_var = tk.StringVar(value="9600")
        self.command_var = tk.StringVar(value="MSG")
        self.payload_var = tk.StringVar(value="Hello Nucleo")
        self.batch_interval_var = tk.StringVar(value="100")
        self.ack_timeout_var = tk.StringVar(value="800")
        self.status_var = tk.StringVar(value="Stopped")
        self.next_sequence = 1

        self._build_window()
        self.refresh_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)

    def _build_window(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(9, weight=1)

        ttk.Label(frame, text="FT232RL COM port:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        self.port_box = ttk.Combobox(frame, textvariable=self.port_var, state="normal")
        self.port_box.grid(row=0, column=1, sticky="ew", pady=5)
        self.refresh_button = ttk.Button(frame, text="Refresh", command=self.refresh_ports)
        self.refresh_button.grid(row=0, column=2, padx=(8, 0), pady=5)

        ttk.Label(frame, text="Board's current baud:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        self.current_baud_box = ttk.Combobox(
            frame,
            textvariable=self.current_baud_var,
            values=tuple(str(rate) for rate in BAUD_RATES),
            state="readonly",
            width=12,
        )
        self.current_baud_box.grid(row=1, column=1, sticky="w", pady=5)

        ttk.Label(frame, text="Set board baud to:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=5)
        self.baud_box = ttk.Combobox(
            frame,
            textvariable=self.baud_var,
            values=tuple(str(rate) for rate in BAUD_RATES),
            state="readonly",
            width=12,
        )
        self.baud_box.grid(row=2, column=1, sticky="w", pady=5)

        ttk.Label(frame, text="Command:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=5)
        self.command_entry = ttk.Entry(frame, textvariable=self.command_var, width=24)
        self.command_entry.grid(row=3, column=1, sticky="w", pady=5)

        ttk.Label(frame, text="Payload:").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=5)
        self.payload_entry = ttk.Entry(frame, textvariable=self.payload_var)
        self.payload_entry.grid(row=4, column=1, columnspan=2, sticky="ew", pady=5)

        ttk.Label(frame, text="Batch interval (ms):").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=5)
        self.batch_interval_entry = ttk.Entry(frame, textvariable=self.batch_interval_var, width=12)
        self.batch_interval_entry.grid(row=5, column=1, sticky="w", pady=5)

        ttk.Label(frame, text="ACK timeout per command (ms):").grid(row=6, column=0, sticky="w", padx=(0, 8), pady=5)
        self.ack_timeout_entry = ttk.Entry(frame, textvariable=self.ack_timeout_var, width=12)
        self.ack_timeout_entry.grid(row=6, column=1, sticky="w", pady=5)

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8, 5))
        self.start_button = ttk.Button(buttons, text="Start continuous", command=self.start)
        self.start_button.pack(side="left")
        self.batch_button = ttk.Button(buttons, text="Send 5-command batch", command=self.start_batch)
        self.batch_button.pack(side="left", padx=(8, 0))
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        ttk.Label(buttons, textvariable=self.status_var).pack(side="right")

        ttk.Label(frame, text="Serial log:").grid(row=8, column=0, columnspan=3, sticky="sw", pady=(8, 3))
        self.log = tk.Text(frame, height=14, wrap="word", state="disabled")
        self.log.grid(row=9, column=0, columnspan=3, sticky="nsew")

        ttk.Label(
            frame,
            text="Batch sends five copies of the selected command, spaced by the interval. Timeout is per command. Request/reply lines use CMD/ACK/NACK; board starts at 9600 after reset.",
            wraplength=700,
        ).grid(row=10, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def refresh_ports(self) -> None:
        selected = self.port_var.get().strip()
        ports = list(list_ports.comports())
        self.port_box["values"] = [port.device for port in ports]
        if selected:
            self.port_var.set(selected)
        elif ports:
            self.port_var.set(ports[0].device)
        else:
            self.port_var.set("")
            self.status_var.set("No serial ports found; connect the adapter or enter a port name")

    def start(self) -> None:
        self._start(mode="continuous")

    def start_batch(self) -> None:
        self._start(mode="batch")

    def _start(self, mode: str) -> None:
        port = self.port_var.get().strip()
        command_name = self.command_var.get().strip().upper()
        payload = self.payload_var.get()

        if not port:
            messagebox.showerror("Serial port required", "Select or enter a port, for example COM5.")
            return
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,23}", command_name):
            messagebox.showerror(
                "Invalid command",
                "Use 1–24 letters, digits, or underscores; the first character must be a letter.",
            )
            return
        if command_name == "SET_BAUD":
            messagebox.showerror(
                "Reserved command",
                "Use the baud-rate selector to change baud; SET_BAUD is reserved for that handshake.",
            )
            return
        if "\n" in payload or "\r" in payload:
            messagebox.showerror("Invalid payload", "The payload cannot contain a newline.")
            return
        try:
            payload_bytes = payload.encode("utf-8")
        except UnicodeEncodeError as exc:
            messagebox.showerror("Invalid message", str(exc))
            return
        if len(payload_bytes) > MAX_PAYLOAD_BYTES:
            messagebox.showerror(
                "Payload too long",
                f"Keep the UTF-8 payload at or below {MAX_PAYLOAD_BYTES} bytes for the STM32 line buffer.",
            )
            return

        try:
            current_baud = int(self.current_baud_var.get())
            baud_rate = int(self.baud_var.get())
        except ValueError:
            messagebox.showerror("Invalid baud rate", "Choose a baud rate from the list.")
            return

        try:
            interval_ms = int(self.batch_interval_var.get())
            ack_timeout_ms = int(self.ack_timeout_var.get())
        except ValueError:
            messagebox.showerror("Invalid timing", "Enter whole-number milliseconds for interval and timeout.")
            return
        if interval_ms < 0 or interval_ms > 60000:
            messagebox.showerror("Invalid interval", "Batch interval must be between 0 and 60000 ms.")
            return
        if ack_timeout_ms < 1 or ack_timeout_ms > 60000:
            messagebox.showerror("Invalid timeout", "ACK timeout must be between 1 and 60000 ms.")
            return

        self.stop_event.clear()
        self._set_running_controls(True)
        action = "batch" if mode == "batch" else "continuous transmission"
        self.status_var.set(f"Opening {port} at {current_baud} baud for {action}…")
        self.worker = threading.Thread(
            target=self._serial_worker,
            args=(port, current_baud, baud_rate, command_name, payload_bytes, mode, interval_ms, ack_timeout_ms),
            daemon=True,
        )
        self.worker.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.status_var.set("Stopping…")
        self.stop_button.configure(state="disabled")

    def _serial_worker(
        self,
        port: str,
        current_baud: int,
        baud_rate: int,
        command_name: str,
        payload: bytes,
        mode: str,
        interval_ms: int,
        ack_timeout_ms: int,
    ) -> None:
        try:
            with serial.Serial(
                port=port,
                baudrate=current_baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=SERIAL_READ_TIMEOUT_SECONDS,
                write_timeout=1.0,
            ) as connection:
                self._post_ui(self.status_var.set, f"Connected: {port} at {current_baud} baud")
                self._post_ui(self._append_log, f"Connected to {port} at {current_baud} baud (8-N-1).")

                if baud_rate != current_baud:
                    baud_command = f"CMD,0000,SET_BAUD,{baud_rate}\n".encode("ascii")
                    connection.write(baud_command)
                    connection.flush()
                    self._post_ui(self._append_log, f"TX  CMD,0000,SET_BAUD,{baud_rate}")

                    baud_reply = self._wait_for_response(
                        connection,
                        "0000",
                        timeout=ack_timeout_ms / 1000.0,
                    )

                    if self.stop_event.is_set():
                        return
                    if baud_reply is None:
                        raise RuntimeError(
                            "No ACK for SET_BAUD. Implement the command/ACK format in the STM32 firmware "
                            "and confirm the current baud matches the board."
                        )
                    baud_fields = [field.strip() for field in baud_reply.split(",")]
                    if baud_fields and baud_fields[0] == "NACK":
                        raise RuntimeError(f"Board rejected SET_BAUD: {baud_reply}")
                    if (
                        len(baud_fields) != 5
                        or baud_fields[0:4] != ["ACK", "0000", "OK", "BAUD"]
                        or baud_fields[4] != str(baud_rate)
                    ):
                        raise RuntimeError(f"Unexpected baud-change reply: {baud_reply}")

                    # The board switches immediately after sending its acknowledgement.
                    connection.baudrate = baud_rate
                    connection.reset_input_buffer()
                    self._post_ui(self.current_baud_var.set, str(baud_rate))
                    self._post_ui(self.status_var.set, f"Board and PC switched to {baud_rate} baud")
                    self._post_ui(self._append_log, f"Baud rate changed to {baud_rate}.")

                if mode == "batch":
                    result = self._send_batch(
                        connection,
                        command_name,
                        payload,
                        interval_ms,
                        ack_timeout_ms,
                    )
                    self._post_ui(self._show_batch_result, result)
                    return

                next_send = time.monotonic()
                while not self.stop_event.is_set():
                    now = time.monotonic()
                    if now < next_send:
                        self.stop_event.wait(min(next_send - now, 0.02))
                        continue

                    sequence = f"{self.next_sequence:04d}"
                    self.next_sequence = 1 if self.next_sequence >= 9999 else self.next_sequence + 1
                    frame = b"CMD," + sequence.encode("ascii") + b"," + command_name.encode("ascii") + b"," + payload + b"\n"
                    connection.write(frame)
                    connection.flush()
                    self._post_ui(
                        self._append_log,
                        f"TX  CMD,{sequence},{command_name},{payload.decode('utf-8')}",
                    )

                    reply = self._wait_for_response(connection, sequence, ack_timeout_ms / 1000.0)
                    if reply is None:
                        self._post_ui(self._append_log, f"TIMEOUT  sequence {sequence}")
                    elif reply.startswith("NACK,"):
                        self._post_ui(self._append_log, f"BOARD REJECTED  {reply}")

                    next_send = max(next_send + SEND_INTERVAL_SECONDS, time.monotonic() + 0.001)
        except (serial.SerialException, OSError, ValueError, RuntimeError) as exc:
            error_text = str(exc)
            if "access is denied" in error_text.lower() or isinstance(exc, PermissionError):
                error_text += " Close other programs using this COM port, then try again."
            self._post_ui(self._append_log, f"ERROR  {error_text}")
            self._post_ui(self.status_var.set, "Connection error")
        finally:
            self._post_ui(self._worker_finished)

    def _worker_finished(self) -> None:
        self._set_running_controls(False)
        if not self.closing and self.status_var.get() != "Connection error":
            self.status_var.set("Stopped")

    def _set_running_controls(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.port_box.configure(state=state)
        self.current_baud_box.configure(state="disabled" if running else "readonly")
        self.baud_box.configure(state="disabled" if running else "readonly")
        self.command_entry.configure(state=state)
        self.payload_entry.configure(state=state)
        self.batch_interval_entry.configure(state=state)
        self.ack_timeout_entry.configure(state=state)
        self.refresh_button.configure(state=state)
        self.start_button.configure(state="disabled" if running else "normal")
        self.batch_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def _append_log(self, text: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{timestamp}] {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _send_batch(self, connection, command_name: str, payload: bytes, interval_ms: int, ack_timeout_ms: int) -> dict:
        pending: dict[str, float] = {}
        expired: set[str] = set()
        rtts_ms: list[tuple[str, float]] = []
        sent_count = 0
        ack_count = 0
        nack_count = 0
        timeout_count = 0
        first_send_time: float | None = None
        next_send_time = time.monotonic()
        interval_seconds = interval_ms / 1000.0
        timeout_seconds = ack_timeout_ms / 1000.0

        while not self.stop_event.is_set() and (sent_count < COMMANDS_PER_BATCH or pending):
            now = time.monotonic()

            if sent_count < COMMANDS_PER_BATCH and now >= next_send_time:
                sequence = f"{self.next_sequence:04d}"
                self.next_sequence = 1 if self.next_sequence >= 9999 else self.next_sequence + 1
                frame = (
                    b"CMD,"
                    + sequence.encode("ascii")
                    + b"," + command_name.encode("ascii")
                    + b"," + payload
                    + b"\n"
                )
                connection.write(frame)
                connection.flush()

                sent_at = time.monotonic()
                if first_send_time is None:
                    first_send_time = sent_at
                pending[sequence] = sent_at
                sent_count += 1
                next_send_time = sent_at + interval_seconds
                self._post_ui(
                    self._append_log,
                    f"TX  CMD,{sequence},{command_name},{payload.decode('utf-8')}",
                )

            raw_reply = connection.readline()
            now = time.monotonic()
            if raw_reply:
                reply = raw_reply.decode("utf-8", errors="replace").rstrip("\r\n")
                self._post_ui(self._append_log, f"RX  {reply}")
                fields = [field.strip() for field in reply.split(",", 3)]
                if len(fields) >= 3 and fields[0] in ("ACK", "NACK"):
                    sequence = fields[1]
                    if sequence in pending:
                        sent_at = pending.pop(sequence)
                        rtt_ms = (now - sent_at) * 1000.0
                        if rtt_ms > ack_timeout_ms:
                            timeout_count += 1
                            expired.add(sequence)
                            self._post_ui(self._append_log, f"LATE  sequence {sequence}, {rtt_ms:.1f} ms")
                        elif fields[0] == "ACK" and fields[2] == "OK":
                            ack_count += 1
                            rtts_ms.append((sequence, rtt_ms))
                            self._post_ui(self._append_log, f"ACK  sequence {sequence} in {rtt_ms:.1f} ms")
                        else:
                            nack_count += 1
                            self._post_ui(self._append_log, f"NACK  sequence {sequence}: {reply}")
                    elif sequence in expired:
                        self._post_ui(self._append_log, f"LATE RX  sequence {sequence}")

            now = time.monotonic()
            for sequence, sent_at in list(pending.items()):
                if now - sent_at >= timeout_seconds:
                    del pending[sequence]
                    expired.add(sequence)
                    timeout_count += 1
                    self._post_ui(self._append_log, f"TIMEOUT  sequence {sequence}")

        finished_at = time.monotonic()
        elapsed_ms = 0.0 if first_send_time is None else (finished_at - first_send_time) * 1000.0
        return {
            "sent": sent_count,
            "acks": ack_count,
            "nacks": nack_count,
            "timeouts": timeout_count,
            "elapsed_ms": elapsed_ms,
            "rtts_ms": rtts_ms,
            "stopped": self.stop_event.is_set(),
        }

    def _show_batch_result(self, result: dict) -> None:
        all_acked = result["acks"] == COMMANDS_PER_BATCH and not result["stopped"]
        title = "Batch complete" if not result["stopped"] else "Batch stopped"
        if all_acked:
            headline = f"All {COMMANDS_PER_BATCH} ACKs received in {result['elapsed_ms']:.1f} ms."
        else:
            headline = f"Successful ACKs: {result['acks']}/{COMMANDS_PER_BATCH}."

        lines = [
            headline,
            f"Commands sent: {result['sent']}/{COMMANDS_PER_BATCH}",
            f"NACKs: {result['nacks']}",
            f"Timeouts: {result['timeouts']}",
            f"Elapsed from first send: {result['elapsed_ms']:.1f} ms",
        ]
        if result["rtts_ms"]:
            rtts = ", ".join(f"{sequence}: {rtt:.1f} ms" for sequence, rtt in result["rtts_ms"])
            lines.append(f"ACK round-trip times: {rtts}")

        summary = "\n".join(lines)
        self.status_var.set(f"Batch: {result['acks']}/{COMMANDS_PER_BATCH} ACKs")
        if all_acked:
            messagebox.showinfo(title, summary)
        else:
            messagebox.showwarning(title, summary)

    def _wait_for_response(self, connection, expected_sequence: str, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        while not self.stop_event.is_set() and time.monotonic() < deadline:
            raw_reply = connection.readline()
            if not raw_reply:
                continue

            reply = raw_reply.decode("utf-8", errors="replace").rstrip("\r\n")
            self._post_ui(self._append_log, f"RX  {reply}")
            fields = [field.strip() for field in reply.split(",", 3)]
            if len(fields) >= 3 and fields[0] in ("ACK", "NACK") and fields[1] == expected_sequence:
                return reply
        return None

    def _post_ui(self, callback, *args) -> None:
        if self.closing:
            return
        try:
            self.root.after(0, callback, *args)
        except tk.TclError:
            # The window may have been closed while the serial thread was finishing.
            pass

    def close_window(self) -> None:
        self.closing = True
        self.stop_event.set()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    SerialTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()

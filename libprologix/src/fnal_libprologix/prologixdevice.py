#Generic Prologix#

from __future__ import annotations
import socket
import select
import time

#Class for devices which are controlled using a Prologix Ethernet-to-GPIB
# Converter/Bridge
# Docs: https://prologix.biz/downloads/PrologixGpibEthernetManual.pdf
class PrologixDevice():
    DEF_BUFFER_SIZE: Final = 4096

    MODE_DEVICE: Final = 0
    MODE_CONTROLLER: Final = 1

    def __init__(self, logger, ip_address, device_addr, default_data_timeout = 2):
        self.log = logger
        self.ip_address = ip_address
        self.device_addr = device_addr
        self.data_timeout = default_data_timeout
        self.data_eot_char = None # see set_eot_signaling()

        self.sock = None

    def connect(self, max_attempts = 10, tcp_timeout = 0.5) -> bool:
        if not self.__open_bridge_connection():
            return False

        self._flush_buffer()
        try: # all commands here CAN fail (e.g. identify_*)
            ident = self.identify_bridge()
            if not ident.startswith("Prologix GPIB-ETHERNET Controller"):
                print(f"Prologix handshake failure. Not a Prologix device? Identity: {ident}")
                self.disconnect()
                return False
            print(f"Connected to Prologix bridge: {ident}")

            self.set_mode(self.MODE_CONTROLLER)
            self.set_gpib_addr(self.device_addr)
            #AQ 5/15/2023 -- When sending NON-QUERY commands, this needs to be false, or
            #else every command will be sent like a query, and the device will throw an
            #error -420 Query UNTERMINATED.
            #GH 5/18/2023 -- In real life this should ALWAYS be disable if we want to do
            # async I/O. Now we use "++read eoi" to utilize GPIB interrupt singaling
            self.set_read_after_write(enabled=False)

            # This can let us avoid delays in socket select when reading anything from
            # the GPIB device. Not finished yet.
            #self.set_eot_signaling(True)

            ident = self.identify_device()
            print(f"Connected to GPIB device: {ident}")

        except Exception as e:
            print(e)
            print(f"I/O error: {str(e)}")
            self.disconnect()
            return False

        return True

    def __open_bridge_connection(self, max_attempts = 10, tcp_timeout = 0.5) -> bool:
        self.disconnect()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        sock.settimeout(tcp_timeout) # the connection timeout is not the same as send/rcv timeout!

        print(f"Attempting Prologix connection (up to {max_attempts} times)")
        for _ in range(1, max_attempts):
            try:
                #All prologix converters connect to port 1234 and it cannot be changed
                sock.connect((self.ip_address, 1234))

            except Exception as e:
                print(f"Prologix TCP connection failed: {str(e)}")
                continue

            self.sock = sock
            return True

        print("Exhausted Prologix connection attempts!")
        return False

    def disconnect(self) -> None:
        if not self.is_connected():
            return # noop

        print(f"Disconnecting from Prologix...")
        self.sock.close()
        self.sock = None

    def is_connected(self) -> bool:
        return self.sock is not None

    def identify_bridge(self) -> str:
        """Identify Prologix bridge"""
        return self.send_command("ver", True)

    def identify_device(self) -> str:
        """Identifies GPIB device connected"""
        return self.query("*idn?", True)

    def set_mode(self, mode: int) -> None:
        """Set Prologic operating mode. Use MODE_* constants."""
        self.send_command(f"mode {mode}", False)

    def set_gpib_addr(self, addr: int) -> None:
        self.send_command(f"addr {addr}", False)

    def set_read_after_write(self, enabled: bool = True) -> None:
        """Enables/disabled Prologix Read-After-Write"""
        self.send_command(f"auto {1 if enabled else 0}", False)

    def set_local_controls(self, enabled: bool = True) -> None:
        """Enables/disabled GPIB device local front panel controls"""
        if enabled:
            self.send_command('loc', False)
        else:
            self.send_command('llo', False)

    def set_eot_signaling(self, enabled: bool = False, char_code: int = 0x04) -> None:
        if not enabled:
            self.send_command("eot_enable 0", False)
            return

        if (char_code < 0 or char_code > 255):
            raise ValueError(f"EOT character must be beteen 0 and 255 inclusively (got {char_code})")

        self.data_eot_char = char_code
        self.send_command(f"eot_char {char_code}", False)
        self.send_command(f"eot_enable 1", False)
    
    def send_line(self, cmd_txt: str):
        if not self.is_connected():
            raise RuntimeError("Attempted to send_line() but not connected")
        
        #print(f"SENDING: {cmd_txt}")
        self.sock.send((cmd_txt+"\n").encode())

    def send_command(self, cmd: str, expect_response: bool) -> str | None:
        cmd = f"++{cmd}"

        # Even silent commands in Prolgoix can return an error but quickly
        self.send_line(cmd)
        rcv = self.recv_line() if expect_response else self.recv_blocking(0.1)
        rcv = rcv.strip()

        # Prologix will send this string no matter what (e.g. wrong parameter to a valid command)
        if rcv == "Unrecognized command":
            raise IOError(f"Prologix command \"{cmd}\": bridge failed to excute the commend")

        if not expect_response and rcv != "":
            raise RuntimeError(f"Prologic command \"{cmd}\" returned data when not expected: {rcv}")

        return rcv if expect_response else None

    def _flush_buffer(self) -> None:
        """Forcefully flushes Prologix receive buffer

           This is a low-level function, meant to deal with a
           semi-buggy behavior of the interface. You should NOT be
           using it unless you're 100% sure you need it, as it can
           lead to data loss. Definitely DO NOT use it from outside
           of the Prologix handling code.
        """
        # Prologix will hold up to 1 frame of GPIB data
        # If not picked-up further commands are sometimes ignores
        #  until the buffer is freed
        try:
            # we only want to get th data from buffer, not wait for new data
            self.sock.settimeout(0.02)
            while True:
                rcv = self.sock.recv(1024)
                if rcv.len() != 1024:
                    return

        except TimeoutError:
            pass

    def recv_line(self, max_timeout: int|None = None) -> str:
        """High-level socket line-aware receive function using asynchronous I/O

           This function will read data from the socket until a full \n-terminated line is
           received. If no data is present it may block up to 50ms.
        """
        if not self.is_connected():
            raise RuntimeError("Attempted to recv_line() but not connected")

        if max_timeout is None:
            max_timeout = self.data_timeout

        buffer = ""

        self.sock.setblocking(False) # this also sets socket timeout to 0
        time_in = time.monotonic()
        while True:
            if time.monotonic() - time_in > max_timeout:
                break

            r, w, e = select.select([self.sock], [], [], max_timeout if max_timeout < 0.05 else 0.05)
            if not r: # async timeout reached as per Python docs if the list is empty
                continue

            rcv = self.sock.recv(self.DEF_BUFFER_SIZE).decode()

            buffer = f"{buffer}{rcv}"
            #print(f"BUFFER: >>{buffer}<<")
            if "\n" in buffer:
                break

        return buffer

    def recv_blocking(self, max_timeout: int|None = None, max_bytes: int|None = None) -> str:
        """Low-level socket receive function using blocking I/O

           This function will block up to the timeout specified (defaulting to one set during
           init). This is probably not what you want. You probably want to use recv_line() that
           works asynchornously.

           This function will block until timeout is reached if no data is present on the socket.
        """
        if not self.is_connected():
            raise RuntimeError("Attempted to recv() but not connected")

        if max_bytes is None:
            max_bytes = self.DEF_BUFFER_SIZE

        self.sock.settimeout(self.data_timeout if max_timeout is None else max_timeout)
        try:
            rcv = self.sock.recv(max_bytes)
        except TimeoutError: # this is expected if nothing was present in the OS buffer
            return ''

        return rcv.decode()

    def query(self, cmd_txt: str, trim: bool = False):
        #For Query-type commands ONLY we set read-after-write to True. 
        #self.(enabled=True)
        self.send_line(cmd_txt)

        recv = self.send_command("read", True)
        #recv = self.recv_line()
        #self.set_read_after_write(enabled=False)

        return recv.strip() if trim else recv

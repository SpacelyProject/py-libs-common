from __future__ import annotations
import socket
from fnal_libIO import *
import select
import time


class IPInterface(GenericInterface):
    DEF_BUFFER_SIZE: Final = 4096

    # __init__() --> Should initialize the connection to the device.
    def __init__(self, logger, ip_address, port, default_data_timeout = 2):
        self.log = logger
        self.ip_address = ip_address
        self.data_timeout = default_data_timeout
        self.port = port
        self.sock = None

        self.connect()

    def set_timeout(self, timeout):
        self.sock.settimeout(timeout)
    
    def connect(self, max_attempts = 10, tcp_timeout = 0.5) -> bool:
        self.disconnect()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        sock.settimeout(tcp_timeout)

        self.log.info(f"Attempting IP Interface connection (up to {max_attempts} times)")
        for _ in range(1, max_attempts):
            try:
                #All prologix converters connect to port 1234 and it cannot be changed
                sock.connect((self.ip_address, self.port))

            except Exception as e:
                self.log.error(f"IP Interface connection failed: {str(e)} - retrying")
                time.sleep(1)
                continue

            self.sock = sock
            return True

        self.log.error("Exhausted IP Interface connection attempts!")
        return False


    def disconnect(self) -> None:
        if not self.is_connected():
            return # noop

        self.log.info("Disconnecting from IP Interface...")
        self.sock.close()
        self.sock = None

    def is_connected(self) -> bool:
        return self.sock is not None


    # write() --> Should write a line w/o expecting a response.
    def write(self, write_txt):
        if not self.is_connected():
            raise RuntimeError("Attempted to send_line() but not connected")

        cmd_txt = write_txt.strip()  # some instruments will error-out when whitespaces are sent
        if '\n' in cmd_txt or '\r' in cmd_txt:
            raise ValueError("Your line command contains a new line character. "
                             "You should NOT try to chain multiple commands in one call, "
                             "as it can interfeer with the proper oepration of the interface.")

        
        self.sock.send((cmd_txt+"\n").encode())
        
    # query() --> Should write a line and read back the response.
    def query(self, query_text):
        self.write(query_text)
        return self.recv_line()
        
        
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

            #self.log.debug(f"PrologixDevice recv_line buffer: >>{buffer}<<")
            if "\n" in buffer or "\r" in buffer:
                break

        return buffer
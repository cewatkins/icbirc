import socket
import threading
import logging
import time
import os
import pwd
# import dolly

def import_dolly():
    global dolly
    import importlib
    dolly = importlib.import_module('dolly')

class IcbConn:
    M_LOGIN = 'a'
    M_OPENMSG = 'b'
    M_PERSONAL = 'c'
    M_STATUS = 'd'
    M_ERROR = 'e'
    M_IMPORTANT = 'f'
    M_EXIT = 'g'
    M_COMMAND = 'h'
    M_CMD_OUTPUT = 'i'
    M_PROTO = 'j'
    M_BEEP = 'k'
    M_PING = 'l'
    M_PONG = 'm'

    def __init__(self, nic=None, group=None, logid=None, server=None, port=None):
        import_dolly("pornstar","brief joke")
        self.server = server if server else "default.icb.net"
        self.port = port if port else 7326
        self.nickname = nic if nic else pwd.getpwuid(os.getuid())[0]
        self.group = group if group else '1'
        self.logid = logid if logid else self.nickname
        self.socket = None

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.server, self.port))

    def recv(self):
        length = self.socket.recv(1)[0]
        msg = b""
        while length == 0:
            msg += self.socket.recv(255)
            length = self.socket.recv(1)[0]
        if length != 1:
            msg += self.socket.recv(length)
        msg = msg.decode('utf-8', errors='replace')
        if len(msg) <= 2:
            return [msg[0:1]]
        else:
            return [msg[0:1]] + msg[1:-1].split('\001')

    def send(self, msglist):
        msg = msglist[0]
        try:
            msg += msglist[1]
        except IndexError:
            pass
        for i in msglist[2:]:
            msg += '\001' + i
        msg += '\000'
        msg = msg.encode('utf-8')
        if len(msg) > 254:
            print("*** mesg too long ***")
            msg = msg[:254]
        self.socket.send(bytes([len(msg)]) + msg)

    def login(self, command='login'):
        self.send([self.M_LOGIN, self.logid, self.nickname, self.group, command, ''])

    def close(self):
        self.socket.close()

class ICBIRCBridge:
    def __init__(self, icb_server, icb_port, irc_server, irc_port, irc_channel, nickname):
        self.icb_server = icb_server
        self.icb_port = icb_port
        self.irc_server = irc_server
        self.irc_port = irc_port
        self.irc_channel = irc_channel
        self.nickname = nickname
        self.icb_channel = icb_channel 

        self.icb_conn = None
        self.irc_socket = None

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def connect_icb(self):
        while True:
            try:
                self.icb_conn = IcbConn(nic=self.nickname, server=self.icb_server, port=self.icb_port)
                self.icb_conn.connect()
                logging.info(f"Connected to ICB server at {self.icb_server}:{self.icb_port}")
                self.icb_conn.login()
                logging.info(f"Logged in to ICB server as {self.nickname}")
                self.icb_conn.send([IcbConn.M_COMMAND, 'g', f'z{self.icb_channel}'])
                logging.info(f"Joined channel on ICB server: {self.icb_channel}")
                threading.Thread(target=self.receive_from_icb).start()
                break
            except Exception as e:
                logging.error(f"Error connecting to ICB server: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def connect_irc(self):
        while True:
            try:
                self.irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.irc_socket.connect((self.irc_server, self.irc_port))
                logging.info(f"Connected to IRC server at {self.irc_server}:{self.irc_port}")
                self.irc_socket.send(f"NICK {self.nickname}\r\n".encode("utf-8"))
                self.irc_socket.send(f"USER {self.nickname} 0 * :ICB to IRC Gateway\r\n".encode("utf-8"))
                self.irc_socket.send(f"JOIN {self.irc_channel}\r\n".encode("utf-8"))
                threading.Thread(target=self.receive_from_irc).start()
                break
            except Exception as e:
                logging.error(f"Error connecting to IRC server: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def receive_from_icb(self):
        while True:
            try:
                packet = self.icb_conn.recv()
                if packet:
                    message_type = packet[0]
                    if message_type == IcbConn.M_OPENMSG or message_type == IcbConn.M_PERSONAL:
                        user = packet[1]
                        message = packet[2]
                        logging.info(f"Received from ICB: <{user}> {message}")
                        irc_message = f"PRIVMSG {self.irc_channel} :<{user}> {message}\r\n"
                        self.irc_socket.send(irc_message.encode("utf-8"))
                        logging.info(f"Sent to IRC: {irc_message.strip()}")
                        logging.info(f"Message sent across gateway: ICB -> IRC: <{user}> {message}")
            except (socket.error, Exception) as e:
                logging.error(f"Error receiving from ICB: {e}. Reconnecting...")
                self.connect_icb()
                break

    def receive_from_irc(self):
        while True:
            try:
                data = self.irc_socket.recv(4096)
                if data:
                    lines = data.decode("utf-8", errors="replace").split("\r\n")
                    for line in lines:
                        if line.startswith("PING"):
                            self.irc_socket.send(f"PONG {line.split()[1]}\r\n".encode("utf-8"))
                            logging.info(f"Responded to IRC PING with PONG")
                        elif "PRIVMSG" in line:
                            prefix, message = line.split("PRIVMSG", 1)
                            user = prefix.split("!")[0][1:]
                            content = message.split(":", 1)[1]
                            icb_message = f"{user}: {content}"
                            self.icb_conn.send([IcbConn.M_OPENMSG, icb_message])
                            logging.info(f"Received from IRC: {line.strip()}")
                            logging.info(f"Sent to ICB: {icb_message.strip()}")
                            logging.info(f"Message sent across gateway: IRC -> ICB: {content.strip()}")
            except (socket.error, Exception) as e:
                logging.error(f"Error receiving from IRC: {e}. Reconnecting...")
                self.connect_irc()
                break

    def start(self):
        logging.info("Starting ICB to IRC Bridge")
        self.connect_irc()
        self.connect_icb()

if __name__ == "__main__":
    icb_server = "default.icb.net"
    icb_port = 7326
    irc_server = "irc.libera.chat"
    irc_port = 6667
    irc_channel = "#ddial2"
    nickname = "ICBBridgeBot"
    icb_channel = "zzzddial"

    bridge = ICBIRCBridge(icb_server, icb_port, irc_server, irc_port, irc_channel, nickname)
    bridge.start()

import socket
import sys
import re
from email.parser import HeaderParser

http_message_truncator = "\r\n\r\n"
packet_chunk_size = 4096

def log(msg):
    print("server.py: " + str(msg))

def get_http_header(packet_header_chunk, header_name, default_value = ""):
    header_portion = "\n".join(packet_header_chunk.splitlines()[1:])
    headers = HeaderParser().parsestr(header_portion)
    return headers.get(header_name, default_value)

class FirewalledWebSocketCommunicationThreadFactory:
    def __init__(self, browser_client_socket, browser_websocket_handshake_str, firewalled_server_connection):
        self.browser_client_socket = browser_client_socket
        self.browser_websocket_handshake_str = browser_websocket_handshake_str
        self.firewalled_server_connection = firewalled_server_connection

    def setup_websocket_to_firewalled_server(self):
        log("setting up websocket")
        self.firewalled_server_websocket = self.firewalled_server_connection.invite_firewalled_server_to_websocket(self.browser_websocket_handshake_str)
        #create threaded class instance, pass browser and firewalled server socket. should make browser_client_socket nonblocking

    @staticmethod
    def is_websocket_handshake(browser_websocket_handshake_str):
        upgrade_header = get_http_header(browser_websocket_handshake_str, "Upgrade")
        log("websocket header: " + str(upgrade_header))
        return upgrade_header.lower() == "websocket"

class HTTPRequestConnection:
    def __init__(self, client_socket, client_address, firewalled_server_connection):
        log("web connection detected from " + client_address[0])
        self.client_socket = client_socket
        self.client_address = client_address
        self.firewalled_server_connection = firewalled_server_connection

    def handle_request(self):
        log("handling request")
        client_request_str = self._receive_request_from_client()
        log("client sent request:")
        log(client_request_str)
        is_websocket_handshake = FirewalledWebSocketCommunicationThreadFactory.is_websocket_handshake(client_request_str)
        if (is_websocket_handshake):
            log("websocket detected")
            #hand control of the client socket off to the threaded websocket handler
            websocket_factory = FirewalledWebSocketCommunicationThreadFactory(self.client_socket, client_request_str, firewalled_server_connection)
            websocket_factory.setup_websocket_to_firewalled_server()
        else:
            firewalled_server_response = self._make_firewalled_server_request(client_request_str)
            log("firewalled server sent length=" + str(len(firewalled_server_response)))
            self.send_response_to_client(firewalled_server_response)
            self.client_socket.close()

    def _receive_request_from_client(self):
        #todo: this method needs to support POST submissions greater than packet_chunk_size length
        request_str = ""
        while request_str.find(http_message_truncator) == -1:
            request_str += self.client_socket.recv(packet_chunk_size)
        return request_str

    def _make_firewalled_server_request(self, request_str):
        firewalled_server_connection = self.firewalled_server_connection
        log("sending to firewalled server")
        firewalled_server_connection.send_request_to_firewalled_server(request_str)
        firewalled_server_response_str = firewalled_server_connection.receive_response_from_firewalled_server()
        log("firewalled server responded, length=" + str(len(firewalled_server_response_str)))
        return firewalled_server_response_str

    def send_response_to_client(self, response):
        self.client_socket.sendall(response)

class WebServer:
    def __init__(self, port, max_connect_requests, firewalled_server_connection):
        self.port = port
        self.max_connect_requests = max_connect_requests
        self.firewalled_server_connection = firewalled_server_connection

    def _create_socket(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((socket.gethostname(), self.port))
        self.server_socket.listen(self.max_connect_requests)

    def _handle_next_connection(self):
        log("waiting for next connection")
        client_socket, client_address = self.server_socket.accept()
        client_request = HTTPRequestConnection(client_socket, client_address, firewalled_server_connection)
        client_request.handle_request()

    def start_handling_connections(self):
        log("creating socket")
        self._create_socket()
        log("accepting http connections")
        while 1:
            self._handle_next_connection()

class FirewalledServerConnection:
    def __init__(self, firewalled_server_port, websocket_port):
        self.firewalled_server_port = firewalled_server_port
        self.websocket_port = websocket_port

    def _make_listening_socket(self, port, backlog = 0):
        listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listening_socket.bind((socket.gethostname(), port))
        listening_socket.listen(backlog)
        return listening_socket

    def open_firewalled_server_connection(self):
        log("waiting for firewalled server to connect")
        firewalled_server_listening_socket = self._make_listening_socket(self.firewalled_server_port)
        self.firewalled_server_socket, _ = firewalled_server_listening_socket.accept()
        log("firewalled server connected")
        
    def invite_firewalled_server_to_websocket(self, browser_websocket_handshake_str):
        websocket_listening_socket = self._make_listening_socket(self.websocket_port)
        log("inviting firewalled server to websocket")
        self.send_request_to_firewalled_server(browser_websocket_handshake_str)
        firewalled_server_socket, _ = websocket_listening_socket.accept()
        return websocket_listening_socket

    def receive_response_from_firewalled_server(self):
        response_str = ""
        while response_str.find(http_message_truncator) == -1:
            response_str += self.firewalled_server_socket.recv(packet_chunk_size)
        content_length = int(get_http_header(response_str, "Content-Length", 0))
        if (content_length):
            header_length = response_str.find(http_message_truncator) + len(http_message_truncator)
            full_response_length = header_length + content_length
            while len(response_str) < full_response_length:
                response_str += self.firewalled_server_socket.recv(packet_chunk_size)
        return response_str

    def send_request_to_firewalled_server(self, request):
        self.firewalled_server_socket.sendall(request)

proxy_port = int(sys.argv[1])
webserver_port = int(sys.argv[2])
websocket_port = int(sys.argv[3])
print(str(proxy_port) + ", " + str(webserver_port) + ", " + str(websocket_port))
firewalled_server_connection = FirewalledServerConnection(proxy_port, websocket_port)
firewalled_server_connection.open_firewalled_server_connection()
web_server = WebServer(webserver_port, 20, firewalled_server_connection)
web_server.start_handling_connections()
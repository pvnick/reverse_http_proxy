#client example
import socket
import json
import time
import re
import sys
import threading
from email.parser import HeaderParser


def log(msg):
    print("connect.py: " + str(msg))

def get_next_request(proxy_socket):
    request_str = ""
    while request_str.find(http_message_truncator) == -1:
        request_str += proxy_socket.recv(4096)
    return request_str

http_message_truncator = "\r\n\r\n"

def get_http_header(packet_header_chunk, header_name, default_value = ""):
    header_portion = "\n".join(packet_header_chunk.splitlines()[1:])
    headers = HeaderParser().parsestr(header_portion)
    return headers.get(header_name, default_value)

class WebSocketCommunicationThread(threading.Thread):
    def __init__(self, local_webserver_socket, proxy_websocket_socket):
        threading.Thread.__init__(self)
        self.local_webserver_socket = local_webserver_socket
        self.proxy_websocket_socket = proxy_websocket_socket

    def run(self):
        print("starting thread, waiting 5 seconds")
        time.sleep(5)
        print("bye")

class WebSocketProxyCommunicationThreadFactory:
    def __init__(self, local_webserver_port, proxy_websocket_port, browser_websocket_handshake_str):
        self.local_webserver_port = local_webserver_port
        self.proxy_websocket_port = proxy_websocket_port
        self.browser_websocket_handshake_str = browser_websocket_handshake_str

    def _connect_to_local_webserver(self):
        # Connect to the server
        self.local_webserver_socket = socket.socket()
        self.local_webserver_socket.connect(('127.0.0.1', self.local_webserver_port))

    def _send_websocket_handshake_to_local_webserver(self):
        self.local_webserver_socket.sendall(self.browser_websocket_handshake_str)

    def _retrieve_local_webserver_handshake_response(self):
        #todo: check that this doesnt fail before opening the socket
        chunk_size = 4096
        response = ""
        while response.find("\r\n\r\n") == -1:
            response += self.local_webserver_socket.recv(chunk_size)        
        self.handshake_response = response
        log("got handshake response:")
        log(self.handshake_response)

    def _open_new_proxy_connection(self):
        self.proxy_websocket_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.proxy_websocket_socket.connect(('localhost', proxy_websocket_port))

    def _send_handshake_response_to_proxy(self):
        self.proxy_websocket_socket.sendall(self.handshake_response)

    def setup_websocket_to_local_webserver(self):
        self._open_new_proxy_connection()
        self._connect_to_local_webserver()
        self._send_websocket_handshake_to_local_webserver()
        self._retrieve_local_webserver_handshake_response()
        self._send_handshake_response_to_proxy()
        log("websocket established, now create the thread")
        websocket_thread = WebSocketCommunicationThread(self.local_webserver_socket, self.proxy_websocket_socket)
        websocket_thread.start()
        #dont do anything else with the sockets once we pass them off to the thread
        
    @staticmethod
    def is_websocket_handshake(browser_websocket_handshake_str):
        upgrade_header = get_http_header(browser_websocket_handshake_str, "Upgrade")
        log("websocket header: " + str(upgrade_header))
        return upgrade_header.lower() == "websocket"


def make_local_webserver_request(port, message):
    # Connect to the server
    webserver_socket = socket.socket()
    webserver_socket.connect(('127.0.0.1', port))
    #webserver_socket.connect(('google.com', 80))
    #webserver_socket.setblocking(1)
    #log("connected, sending message:")
    #log(message)
    # Send an HTTP request
    webserver_socket.sendall(message)
    log("message sent, receiving")

    # Get the response (in several parts, if necessary)
    response = ""
    chunk_size = 4096
    response = ""
    while response.find("\r\n\r\n") == -1:
        response += webserver_socket.recv(chunk_size)
        #log(response)

    content_length = int(get_http_header(response, "Content-Length", 0))
    print("content length=" + str(content_length))
    if (content_length):
        header_length = response.find("\r\n\r\n") + 4
        full_response_length = header_length + content_length
        while len(response) < full_response_length:
            response += webserver_socket.recv(chunk_size)
            #log(response)
        log("header length=" + str(header_length) + ", content length=" + str(content_length) + ", full response length=" + str(full_response_length) + ", actual length=" + str(len(response)))
    
    return response

local_webserver_port = 9999
proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

proxy_port = int(sys.argv[1])
proxy_websocket_port = int(sys.argv[2])
proxy_socket.connect(('localhost', proxy_port))
while 1:
    next_message = get_next_request(proxy_socket)
    log("got message:")
    toHex = (lambda x:" ".join([hex(ord(c))[2:].zfill(2) for c in x]))
    #log(toHex(next_message))
    log(next_message)
    if (WebSocketProxyCommunicationThreadFactory.is_websocket_handshake(next_message)):
        log("websocket handshake detected")
        websocket_factory = WebSocketProxyCommunicationThreadFactory(local_webserver_port, proxy_websocket_port, next_message)
        websocket_factory.setup_websocket_to_local_webserver()
    else:
        #log("sending to server")
        local_webserver_response = make_local_webserver_request(local_webserver_port, next_message.replace("keep-alive", "close"))
        #log("got response:")
        #log(local_webserver_response)
        proxy_socket.sendall(local_webserver_response)
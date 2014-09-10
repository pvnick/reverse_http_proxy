#client example
import socket
import json
import time
import re
import sys
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

def make_local_webserver_request(port, message):
    # Connect to the server
    webserver_socket = socket.socket()
    webserver_socket.connect(('127.0.0.1', port))
    #webserver_socket.connect(('google.com', 80))
    #webserver_socket.setblocking(1)
    #log("connected, sending message:")
    #log(message)
    # Send an HTTP request
    webserver_socket.send(message)
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
proxy_socket.connect(('localhost', proxy_port))
while 1:
    next_message = get_next_request(proxy_socket)
    log("got message:")
    toHex = (lambda x:" ".join([hex(ord(c))[2:].zfill(2) for c in x]))
    #log(toHex(next_message))
    log(next_message)

    #log("sending to server")
    local_webserver_response = make_local_webserver_request(local_webserver_port, next_message.replace("keep-alive", "close"))
    #log("got response:")
    #log(local_webserver_response)
    proxy_socket.send(local_webserver_response)
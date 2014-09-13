import socket
import sys
import time
import select
from email.parser import HeaderParser
import logging
import Queue

class SocketContainer:
    def __init__(self, child_socket = None):
        if child_socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setblocking(0)
        else:
            self._socket = child_socket
        containers_by_socket[self._socket] = self

    def get_socket(self):
        return self._socket

    def debug(self, str):
        child_logger = logger.getChild(self.__class__.__name__)
        child_logger.debug(str)

class ListeningSocketContainer(SocketContainer):
    socket_backlog = 20

    def __init__(self, port):
        super(ListeningSocketContainer, self).__init__()
        self.port = port
        s = self.get_socket()
        s.bind((socket.gethostname(), port))
        s.listen(self.socket_backlog)

    def accept_connection(self):
        client_socket, client_address = self.get_socket().accept()
        self.debug("Connection accepted from %s on port %d" % (client_address[0], self.port))
        return client_socket

class FirewalledServerListeningSocketContainer(ListeningSocketContainer):
    def __init__(self, port):
        super(FirewalledServerListeningSocketContainer, self).__init__(port)
        self.socket_backlog = 0 #there can be only one!

    def wait_for_client_connection(self):
        #temporarily make the listening socket blocking until the client connects
        #when it does, create and return a container for it
        s = self.get_socket()
        s.setblocking(1)
        client_socket = accept_connection()
        #create a container for the client socket
        client_socket_container = FirewalledServerClientSocketContainer(client_socket)
        s.setblocking(0)
        return client_socket_container 

class WebServerListeningSocketContainer(ListeningSocketContainer):
    def __init__(self, port):
        super(WebServerListeningSocketContainer, self).__init__(port)

    def input_ready(self):
        client_socket = accept_connection()
        #create a container for the client socket
        client_socket_container = WebServerClientSocketContainer(client_socket)

class FirewalledServerHTTPListeningSocketContainer(ListeningSocketContainer):
    def __init__(self, port):
        super(FirewalledServerHTTPListeningSocketContainer, self).__init__(port)

    def input_ready(self):
        client_socket = accept_connection()
        #create a container for the client socket
        client_socket_container = FirewalledServerHTTPClientSocketContainer(client_socket)

class ClientSocketContainer(SocketContainer):
    def __init__(self, child_socket, forward_container = None):
        super(ClientSocketContainer, self).__init__(client_socket)
        self.forward_container = forward_container

    def set_forward_container(forward_container):
        self.forward_container = forward_container

    def send_data(data):
        self.debug("send_data: %s" %s)

    def receive_data(self):
        return "foobar"

class FirewalledServerClientSocketContainer(ClientSocketContainer):
    #holds the main firewalled server communication channel
    def __init__(self, client_socket):
        super(FirewalledServerClientSocketContainer, self).__init__(child_socket = client_socket)

class WebServerClientSocketContainer(SocketContainer):
    #holds incomming http requests
    def __init__(self, client_socket):
        super(WebServerClientSocketContainer, self).__init__(child_socket = client_socket)
        #add to queue for waiting on an incomming firewalled server connection
        clients_waiting_for_firewalled_server.put_nowait(self)

    def input_ready(self):
        #xxx what happens if this is a multi-chunk POST?
        if (self.forward_container is not None):
            #tell the firewalled server it has an incomming request
            incomming_data = self.receive_data()
            get_firewalled_server_client().send_data(incomming_data)        
        else:
            incomming_data = self.receive_data()
            self.forward_container.send_data()

class FirewalledServerHTTPClientSocketContainer(SocketContainer):
    #when an http request passed to the firewalled server, it connects here
    def __init__(self, client_socket):
        super(WebServerClientSocketContainer, self).__init__(child_socket = client_socket)
        #link the two clients
        next_http_client = clients_waiting_for_firewalled_server.get_nowait()
        self.set_forward_container(next_http_client)
        next_http_client.set_forward_container(self)

def get_firewalled_server_client():
    return primary_firewalled_server_client_socket_container

containers_by_socket = {}
clients_waiting_for_firewalled_server = Queue.Queue()
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format = log_format)
logger = logging.getLogger('Internet-facing proxy')
logger.setLevel(logging.DEBUG)

http_message_truncator = "\r\n\r\n"
packet_chunk_size = 4096
socket_check_loop_delay = 0.0001

main_firewalled_server_communication_port = int(sys.argv[1])
webserver_port = int(sys.argv[2])
firewalled_server_http_port = int(sys.argv[3])
print(str(firewalled_server_port) + ", " + str(webserver_port) + ", " + str(firewalled_server_http_port))

firewalled_server_listening_socket_container = FirewalledServerListeningSocketContainer(firewalled_server_port)
primary_firewalled_server_client_socket_container = firewalled_server_listening_socket_container.wait_for_client_connection()
webserver_listening_socket_container = WebServerListeningSocketContainer(webserver_port)
firewalled_server_http_listening_socket_container = FirewalledServerHTTPListeningSocketContainer(firewalled_server_http_port)

containers_by_socket[firewalled_server_listening_socket_container.get_socket()] = firewalled_server_listening_socket_container
containers_by_socket[webserver_listening_socket_container.get_socket()] = webserver_listening_socket_container
containers_by_socket[firewalled_server_http_listening_socket_container.get_socket()] = firewalled_server_http_listening_socket_container

while 1:
    time.sleep(socket_check_loop_delay)
    socket_list = containers_by_socket.keys()
    input_ready, output_ready, _ = select.select(socket_list, socket_list, [], 60)
    for input_socket in input_ready:
        socket_container = containers_by_socket[input_socket]
        socket_container.input_ready()
        
"""if self.s == self.server:
            self.on_accept()
            break

        self.data = self.s.recv(buffer_size)
        if len(self.data) == 0:
            self.on_close()
        else:
            self.on_recv()

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
"""
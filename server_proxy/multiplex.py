import socket
import sys
import time
import select
from email.parser import HeaderParser
import logging

class SocketContainer:
    def __init__(self, child_socket = None):
        if child_socket is not None:
            self._socket = child_socket
        else:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setblocking(0)
        containers_by_socket[self._socket] = self

    def get_socket(self):
        return self._socket

    def debug(self, str):
        child_logger = logger.getChild(self.__class__.__name__)
        child_logger.debug(str)

    def warn(self, str):
        child_logger = logger.getChild(self.__class__.__name__)
        child_logger.warn(str)

    def error(self, str):
        child_logger = logger.getChild(self.__class__.__name__)
        child_logger.error(str)
        self.apoptosis()

    def apoptosis():
        child_logger.warn("Apoptosis induced, deleting organelles and removing from container lookup")
        #delete socket reference to remove this container from the loop select
        s = self.get_socket()
        containers_by_socket.pop(s, None)
        s.shutdown()
        s.close()

class Listener(SocketContainer):
    socket_backlog = 20

    def __init__(self, port):
        super(Listener, self).__init__()
        self.port = port
        s = self.get_socket()
        s.bind((socket.gethostname(), port))
        s.listen(self.socket_backlog)

    def accept_connection(self):
        client_socket, client_address = self.get_socket().accept()
        self.debug("Connection accepted from %s on port %d" % (client_address[0], self.port))
        return client_socket, client_address

class FirewalledServerListener(Listener):
    def __init__(self, port):
        super(FirewalledServerListener, self).__init__(port)
        #there can be only one!
        self.socket_backlog = 0
        #waiting for the firewalled server to connect blocks everything else
        s.setblocking(1)

    def wait_for_client_connection(self):
        #when firewalled server connects, create and return a container for it
        s = self.get_socket()
        client_socket, client_address = accept_connection()
        #XXX need to protect against arbitrary connections from untrusted addresses
        #create a container for the client socket
        client_socket_container = FirewalledServerClient(client_socket)
        return client_socket_container

    def input_ready(self):
        #this should not happen
        s = self.get_socket()
        client_socket, client_address = s.accept()
        client_socket.close()
        self.warn("Unexpected connection rejected from %s on port %d" % (client_address[0], self.port))

class WebServerListener(Listener):
    def __init__(self, port):
        super(WebServerListener, self).__init__(port)

    def input_ready(self):
        client_socket, client_address = accept_connection()
        #create a container for the client socket
        client_socket_container = WebServerClient(client_socket)

class FirewalledServerHTTPListener(Listener):
    def __init__(self, port):
        super(FirewalledServerHTTPListener, self).__init__(port)

    def input_ready(self):
        client_socket, client_address = accept_connection()
        #XXX need to protect against arbitrary connections from untrusted addresses
        #create a container for the client socket
        client_socket_container = FirewalledServerHTTPClient(client_socket)

class Client(SocketContainer):
    def __init__(self, child_socket, forward_container = None):
        super(Client, self).__init__(client_socket)
        self.forward_container = forward_container

    def set_forward_container(forward_container):
        self.forward_container = forward_container

    def send_data(data):
        self.debug("send_data: %s" %s)

    def receive_data(self):
        return "foobar"

class FirewalledServerClient(Client):
    #holds the main firewalled server communication channel
    def __init__(self, client_socket):
        super(FirewalledServerClient, self).__init__(child_socket = client_socket)

class WebServerClient(Client):
    #holds incoming http requests
    def __init__(self, client_socket):
        super(WebServerClient, self).__init__(child_socket = client_socket)
        self.tag = self.generate_request_tag()
        #save reference tag so firewalled server connection can unique identify this request
        http_request_clients_by_tag[self.tag] = self
        self.sent_tagged_request = False

    @staticmethod
    def generate_request_tag():
        return str(uuid.uuid4())

    @staticmethod
    def get_client_by_tag(tag):
        return http_request_clients_by_tag.get(tag, None)

    def tag_firewalled_server_bound_request(self, outbound_data):
        #used to identify this socket when the firewalled server connects to us
        newline_index = outbound_data.find("\n")
        tagged_data = outbound_data[:newline_index]
        tagged_data += "\nFirewalled-Server-Request-Tag: %s" self.tag
        tagged_data += outbound_data[:newline_index]
        return tagged_data

    def input_ready(self):
        #xxx what happens if this is a multi-chunk POST?
        incoming_data = self.receive_data()
        if (self.forward_container is not None):
            self.forward_container.send_data(incoming_data)
        elif (self.sent_tagged_request == False):
            #tell the firewalled server it has an incoming request
            outbound_data = tag_firewalled_server_bound_request(incoming_data)
            get_primary_firewalled_server_client().send_data(outbound_data)
            self.sent_tagged_request = True
        else:
            #this is undefined behavior, terminate the connection
            self.error("Received second round of data before connecting to forward container")

class FirewalledServerHTTPClient(Client):
    #when an http request passed to the firewalled server, it connects here
    def __init__(self, client_socket):
        super(FirewalledServerHTTPClient, self).__init__(child_socket = client_socket)

    def link_clients(associated_http_client):
        self.set_forward_container(associated_http_client)
        associated_http_client.set_forward_container(self)

    @staticmethod
    def get_request_tag(incoming_data):
        return "foobar"

    def input_ready(self):
        #xxx what happens if this is a multi-chunk POST?
        incoming_data = self.receive_data()
        if (self.forward_container is not None):
            self.forward_container.send_data(incoming_data)
        else:
            #link the two clients
            request_tag = self.get_request_tag(incoming_data)
            associated_http_client = WebServerClient.get_client_by_tag(request_tag)
            self.link_clients(associated_http_client)

def get_primary_firewalled_server_client():
    return primary_firewalled_server_client

containers_by_socket = {}
http_request_clients_by_tag = {}
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
print(str(WebServerClient) + ", " + str(webserver_port) + ", " + str(firewalled_server_http_port))

primary_firewalled_server_listener = FirewalledServerListener(WebServerClient)
logger.info("Waiting for incomming firewalled server connection on port %d" % main_firewalled_server_communication_port)
primary_firewalled_server_client = firewalled_server_listener.wait_for_client_connection()
#we dont need this anymore
primary_firewalled_server_listener.apoptosis()

webserver_listener = WebServerListener(webserver_port)
firewalled_server_http_listener = FirewalledServerHTTPListener(firewalled_server_http_port)

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
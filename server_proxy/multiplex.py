import socket
import sys
import time
import select
import logging
import http

class SocketContainer(object):
    packet_chunk_size = 4096

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

    def apoptosis(self):
        child_logger = logger.getChild(self.__class__.__name__)
        child_logger.warn("Apoptosis induced. Deleting organelles and removing from container lookup")
        s = self.get_socket()
        #dont include this socket in the looped select anymore
        containers_by_socket.pop(s, None)
        s.shutdown(socket.SHUT_RDWR)
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
        self.get_socket().setblocking(1)

    def wait_for_client_connection(self):
        #when firewalled server connects, create and return a container for it
        client_socket, client_address = self.accept_connection()
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
        client_socket, client_address = self.accept_connection()
        #XXX need to protect against arbitrary connections from untrusted addresses
        #create a container for the client socket
        client_socket_container = EphemeralWebServerClient(client_socket)

class FirewalledServerHTTPListener(Listener):
    def __init__(self, port):
        super(FirewalledServerHTTPListener, self).__init__(port)

    def input_ready(self):
        client_socket, client_address = self.accept_connection()
        #XXX need to protect against arbitrary connections from untrusted addresses
        #create a container for the client socket
        client_socket_container = FirewalledServerHTTPClient(client_socket)

class Client(SocketContainer):
    def __init__(self, child_socket, forward_container = None):
        super(Client, self).__init__(child_socket)
        self.forward_container = forward_container

    def set_forward_container(self, forward_container):
        self.forward_container = forward_container

    def forward_data(self, data):
        if (self.is_forward_linked()):
            self.forward_container.send_data(data)
        else:
            self.error("Attempted data forwarding without forward container")
            raise

    def link_clients(self, associated_client):
        self.set_forward_container(associated_client)
        associated_client.set_forward_container(self)

    def is_forward_linked(self):
        return self.forward_container is not None

    def send_data(self, data):
        self.debug("send_data: %s" % data)
        self.get_socket().sendall(data)

    def receive_data(self, wait_for_full_http_header = False, wait_for_full_http_request = False):
        data = ""
        s = self.get_socket()
        if wait_for_full_http_header:
            while not http.contains_full_header(data):
                data += s.recv(self.packet_chunk_size)
            if wait_for_full_http_request:
                full_request_size = http.get_full_request_size(data)
                while len(data) < full_request_size:
                    data += s.recv(self.packet_chunk_size)
        else:
            data += s.recv(self.packet_chunk_size)
        return data

class FirewalledServerClient(Client):
    #holds the main firewalled server communication channel
    def __init__(self, client_socket):
        super(FirewalledServerClient, self).__init__(child_socket = client_socket)

    def input_ready(self):
        incoming_data = self.receive_data()
        if not incoming_data:
            self.error("Firewalled server closed main connection")
            exit()
        else:
            self.warn("Unexpected data through firewalled server communication channel: %s" % incoming_data)

class EphemeralWebServerClient(Client):
    #holds incoming http requests that quickly die when fulfilled
    #todo: need a way to manually kill the sockets when they arent needed anymore
    def __init__(self, client_socket):
        super(EphemeralWebServerClient, self).__init__(child_socket = client_socket)
        self.sent_tagged_request = False
        #save reference tag so firewalled server connection can unique identify this request
        self.tag = http.generate_request_tag()
        self.debug("Setting request tag: %s" % self.tag)
        http_clients_by_tag[self.tag] = self

    def input_ready(self):
        incoming_data = self.receive_data(True, True)
        #tell the firewalled server it has an incoming request
        outbound_data = http.add_request_tag(incoming_data, self.tag)
        get_primary_firewalled_server_client().send_data(outbound_data)
        self.sent_tagged_request = True
        if (http.is_websocket_handshake(outbound_data)):
            #pass the connection to a persistent client
            websocket_client = PersistentWebsocketClient(self.get_socket(), self.tag)

class PersistentWebsocketClient(Client):
    #holds persistent websocket connection to browser
    def __init__(self, client_socket, tag):
        super(PersistentWebsocketClient, self).__init__(child_socket = client_socket)
        self.tag = tag
        #overwrite the tag lookup to point here
        http_clients_by_tag[tag] = self

    def input_ready(self):
        incoming_data = self.receive_data()
        self.forward_data(incoming_data)

class FirewalledServerHTTPClient(Client):
    #when an http request passed to the firewalled server, it connects here
    def __init__(self, client_socket):
        super(FirewalledServerHTTPClient, self).__init__(child_socket = client_socket)

    def input_ready(self):
        incoming_data = self.receive_data()
        if (not self.is_forward_linked()):
            #link the two clients
            request_tag = http.get_request_tag(incoming_data)
            if request_tag:
                associated_http_client = get_client_by_tag(request_tag)
                self.link_clients(associated_http_client)
            else:
                self.error("Expected request tag")
                return
        self.forward_data(incoming_data)

def get_primary_firewalled_server_client():
    return primary_firewalled_server_client

def get_client_by_tag(tag):
    return http_clients_by_tag.get(tag, None)

containers_by_socket = {}
http_clients_by_tag = {}
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format = log_format)
logger = logging.getLogger('Internet-facing proxy')
logger.setLevel(logging.DEBUG)

packet_chunk_size = 4096
socket_check_loop_delay = 0.0001

main_firewalled_server_communication_port = int(sys.argv[1])
webserver_port = int(sys.argv[2])
firewalled_server_http_port = int(sys.argv[3])
print(str(main_firewalled_server_communication_port) + ", " + str(webserver_port) + ", " + str(firewalled_server_http_port))

primary_firewalled_server_listener = FirewalledServerListener(main_firewalled_server_communication_port)
logger.info("Waiting for incomming firewalled server connection on port %d" % main_firewalled_server_communication_port)
primary_firewalled_server_client = primary_firewalled_server_listener.wait_for_client_connection()
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
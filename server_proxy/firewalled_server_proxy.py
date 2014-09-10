import socket

server_socket = None
client_socket = None
client_address = None
packet_chunk_size = 4096
http_message_truncator = "\r\n\r\n"
request_str = ""

def start_listening(port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((socket.gethostname(), port))
    server_socket.listen(0)
    print(server_socket)

def ensure_server_socket_created():
    print(server_socket)
    if (not server_socket):
        raise Exception("start_listening() must be called before using the proxy")

def ensure_client_socket_created():
    if not server_socket:
        raise Exception("Client must connect before data is sent or requested")

def wait_for_connection_from_firewalled_server():
    ensure_server_socket_created()
    (client_socket, client_address) = server_socket.accept()
    
def receive_response_from_client():
    ensure_client_socket_created()
    request_str = ""
    while request_str.find(http_message_truncator) == -1:
        request_str += client_socket.recv(packet_chunk_size)

def send_request_to_client(request):
    ensure_client_socket_created()
    total_sent = 0
    response_length = len(response)
    while (total_sent < response_length):
        message_chunk_start_index = total_sent
        message_chunk_end_index = total_sent + packet_chunk_size
        chunk = response[message_chunk_start_index:message_chunk_end_index]
        client_socket.send(chunk)
        total_sent += packet_chunk_size
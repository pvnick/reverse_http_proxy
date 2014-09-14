from email.parser import HeaderParser
import uuid

header_truncator = "\r\n\r\n"
request_tag_header_name = "Firewalled-Server-Proxy-Request-Tag"

def get_http_header(packet_header_chunk, header_name, default_value = ""):
    newline_position = packet_header_chunk.find("\n")
    header_portion = packet_header_chunk[newline_position+1:]
    headers = HeaderParser().parsestr(header_portion)
    return headers.get(header_name, default_value)

def contains_full_header(packet_header_chunk):
    return packet_header_chunk.find(header_truncator) != -1

def get_full_request_size(packet_header_chunk):
    content_length = int(get_http_header(packet_header_chunk, "Content-Length", 0))
    header_length = packet_header_chunk.find(header_truncator) + len(header_truncator)
    full_request_size = header_length + content_length
    return full_request_size

def is_websocket_handshake(packet_header_chunk):
    upgrade_header = get_http_header(packet_header_chunk, "Upgrade")
    return upgrade_header.lower() == "websocket"

def get_request_tag(packet_header_chunk):
    tag = get_http_header(packet_header_chunk, request_tag_header_name)
    return tag

def add_request_tag(data, tag):
    newline_index = data.find("\n")
    tagged_data = data[:newline_index]
    tagged_data += "\n%s: %s" % (request_tag_header_name, tag)
    tagged_data += data[newline_index:]
    return tagged_data

def generate_request_tag():
    return str(uuid.uuid4())
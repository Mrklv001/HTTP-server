import socket
import threading
import argparse
import os

# Parse the request data to extract the HTTP method, path and version
def parse_request(request_data):
    lines = request_data.split('\r\n')
    start_line = lines[0]
    method, path, version = start_line.split(' ')

    headers = {}
    for line in lines[1:]:
        if line == "":
            break
        if ": " in line:
            key, value = line.split(": ", 1)
            headers[key] = value

    return method, path, version, headers


# Returns the HTTP response for a given path
def get_response(path, headers):
    accept_encoding = headers.get("Accept-Encoding", "")
    supports_gzip = "gzip" in accept_encoding

    def add_common_headers(body, content_type):
        headers = f"Content-Type: {content_type}\r\nContent-Length: {len(body)}"
        if supports_gzip:
            headers += "\r\nContent-Encoding: gzip"
        return headers

    if path.startswith("/echo/"):
        body = path[len("/echo/"):].encode()
        header_section = add_common_headers(body, "text/plain")
        return f"HTTP/1.1 200 OK\r\n{header_section}\r\n\r\n".encode() + body

    if path == "/user-agent":
        body = headers.get("User-Agent", "").encode()
        header_section = add_common_headers(body, "text/plain")
        return f"HTTP/1.1 200 OK\r\n{header_section}\r\n\r\n".encode() + body

    if path.startswith("/files/"):
        filename = path[len("/files/"):]
        file_path = os.path.join(FILES_DIR, filename)

        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                content = f.read()
            header_section = add_common_headers(content, "application/octet-stream")
            return f"HTTP/1.1 200 OK\r\n{header_section}\r\n\r\n".encode() + content
        else:
            return b"HTTP/1.1 404 Not Found\r\n\r\n"

    if path == "/":
        return b"HTTP/1.1 200 OK\r\n\r\n"

    return b"HTTP/1.1 404 Not Found\r\n\r\n"




# Returns the HTTP response for a given path
def handle_request(client_socket):
    request_data = b""
    
    while b"\r\n\r\n" not in request_data:
        request_data += client_socket.recv(1024)
    
    headers_end = request_data.find(b"\r\n\r\n")
    header_bytes = request_data[:headers_end].decode()
    method, path, version, headers = parse_request(header_bytes)
    
    body = b""
    if method == "POST":
        content_length = int(headers.get("Content-Length", 0))
        body = request_data[headers_end+4:]
        while len(body) < content_length:
            body += client_socket.recv(1024)

        if path.startswith("/files/"):
            filename = path[len("/files/"):]
            file_path = os.path.join(FILES_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(body)
            response = b"HTTP/1.1 201 Created\r\n\r\n"
            client_socket.send(response)
            return

    response = get_response(path, headers)
    if isinstance(response, str):
        response = response.encode()
    client_socket.send(response)




def handle_connection(client_socket):
    try:
        handle_request(client_socket)
    finally:
        client_socket.close()


parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=str, required=False, default='.')
args = parser.parse_args()
FILES_DIR = args.directory


def main():
    server_socket = socket.create_server(("localhost", 4221))
    print("Server is running on port 4221...")

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"Connection from {addr} has been established")

            thread = threading.Thread(target=handle_connection, args=(client_socket,))
            thread.start()

    except KeyboardInterrupt:
        print("\nServer is shutting down.")
    finally:
        server_socket.close()
        print("Server has been shut down.")



if __name__== "__main__":
    main()
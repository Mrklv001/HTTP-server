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
    if path.startswith("/echo/"):
        echo_str = path[len("/echo/"):]
        body = echo_str
        content_type = "Content-Type: text/plain"
        content_length = f"Content-Length: {len(body)}"
        return f"HTTP/1.1 200 OK\r\n{content_type}\r\n{content_length}\r\n\r\n{body}"

    if path == "/user-agent":
        body = headers.get("User-Agent", "")
        content_type = "Content-Type: text/plain"
        content_length = f"Content-Length: {len(body)}"
        return f"HTTP/1.1 200 OK\r\n{content_type}\r\n{content_length}\r\n\r\n{body}"

    if path.startswith("/files/"):
        filename = path[len("/files/"):]
        file_path = os.path.join(FILES_DIR, filename)

        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                content = f.read()
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/octet-stream\r\n"
                f"Content-Length: {len(content)}\r\n"
                "\r\n"
            )
            return headers.encode() + content
        else:
            return b"HTTP/1.1 404 Not Found\r\n\r\n"

    if path == "/":
        return b"HTTP/1.1 200 OK\r\n\r\n"

    return b"HTTP/1.1 404 Not Found\r\n\r\n"




# Returns the HTTP response for a given path
def handle_request(client_socket):
    request_data = client_socket.recv(1024).decode()
    if not request_data:
        return

    method, path, version, headers = parse_request(request_data)
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

            # Create a new thread to process the client
            thread = threading.Thread(target=handle_connection, args=(client_socket,))
            thread.start()

    except KeyboardInterrupt:
        print("\nServer is shutting down.")
    finally:
        server_socket.close()
        print("Server has been shut down.")



if __name__== "__main__":
    main()
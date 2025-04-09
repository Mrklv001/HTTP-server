import socket

# Parse the request data to extract the HTTP method, path and version
def parse_request(request_data):
    lines = request_data.split('\r\n')
    start_line = lines[0]
    method, path, version = start_line.split(' ')

    headers = {}
    for line in lines[1:]:
        if line == "":
            break  # конец заголовков
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
        response = f"HTTP/1.1 200 OK\r\n{content_type}\r\n{content_length}\r\n\r\n{body}"
        return response

    if path == "/user-agent":
        body = headers.get("User-Agent", "")
        content_type = "Content-Type: text/plain"
        content_length = f"Content-Length: {len(body)}"
        response = f"HTTP/1.1 200 OK\r\n{content_type}\r\n{content_length}\r\n\r\n{body}"
        return response

    responses = {
        "/": "HTTP/1.1 200 OK\r\n\r\n",
    }
    default_response = "HTTP/1.1 404 Not Found\r\n\r\n"
    return responses.get(path, default_response)



# Returns the HTTP response for a given path
def handle_request(client_socket):
    request_data = client_socket.recv(1024).decode()
    if not request_data:
        return
    
    method, path, version, headers = parse_request(request_data)
    response = get_response(path, headers)
    client_socket.send(response.encode())


def main():
    server_socket = socket.create_server(("localhost", 4221))
    print("Server is running on port 4221...")

    try:
        while True:
            # Wait for a connection
            print("Wait for a connection...")
            client_socket, addr = server_socket.accept()

            print(f"Connection from {addr} has been established")

            # Handle the client's request
            handle_request(client_socket)

            client_socket.close()
    except KeyboardInterrupt:
        print("\nServer is shutting down.")
    finally:
        server_socket.close()
        print("Server has been shut down.")


if __name__== "__main__":
    main()
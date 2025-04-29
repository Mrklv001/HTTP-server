def handle_echo(path, headers):
    body = path[len("/echo/"):].encode()
    headers = f"Content-Type: text/plain\r\nContent-Length: {len(body)}\r\n"
    response = f"HTTP/1.1 200 OK\r\n{headers}\r\n\r\n".encode() + body
    return response

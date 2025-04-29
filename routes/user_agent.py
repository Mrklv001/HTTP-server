def handle_user_agent(path, headers):
    user_agent = headers.get("User-Agent", "").encode()
    headers = f"Content-Type: text/plain\r\nContent-Length: {len(user_agent)}\r\n"
    response = f"HTTP/1.1 200 OK\r\n{headers}\r\n\r\n".encode() + user_agent
    return response

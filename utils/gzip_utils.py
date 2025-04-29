import gzip


def compress_gzip(body, content_type):
    accept_encoding = headers.get("Accept-Encoding", "")
    supports_gzip = "gzip" in accept_encoding

    if supports_gzip:
        body = gzip.compress(body)
        headers = f"Content-Type: {content_type}\r\nContent-Encoding: gzip\r\nContent-Length: {len(body)}"
    else:
        headers = f"Content-Type: {content_type}\r\nContent-Length: {len(body)}"
    return headers, body

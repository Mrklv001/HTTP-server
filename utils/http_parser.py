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


def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.0f} TB"

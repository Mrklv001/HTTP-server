from .static import handle_static
from .files import handle_files
from .echo import handle_echo
from .user_agent import handle_user_agent

route_handlers = {
    'GET': {
        '/static': handle_static,
        '/files': handle_files,
        '/echo': handle_echo,
        '/user-agent': handle_user_agent,
    },
    'POST': {
        '/files': handle_files,
    },
    'DELETE': {
        '/files': handle_files,
    }
}

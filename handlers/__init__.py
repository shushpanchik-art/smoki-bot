from handlers.admin import router as admin_router
from handlers.group import router as group_router

# Порядок важен: admin (личка/команды) раньше group (широкий фильтр по чату)
ROUTERS = [admin_router, group_router]

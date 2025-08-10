import threading


# Request Scoped Variables
class RequestConfig(threading.local):
    is_slave_allowed = None


request_config = RequestConfig()


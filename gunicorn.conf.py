# Gunicorn production configuration
import multiprocessing
import os

# Server socket
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:5000')
backlog = 2048

# Worker processes
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 2

# Logging
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '/var/log/gunicorn/access.log')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '/var/log/gunicorn/error.log')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'ranshi_kun'

# Server mechanics
daemon = False
pidfile = '/var/run/gunicorn/ranshi_kun.pid'
user = os.environ.get('GUNICORN_USER', 'www-data')
group = os.environ.get('GUNICORN_GROUP', 'www-data')
tmp_upload_dir = None

# SSL (if needed)
keyfile = os.environ.get('SSL_KEY_PATH')
certfile = os.environ.get('SSL_CERT_PATH')

# Monitoring
statsd_host = os.environ.get('STATSD_HOST')
statsd_prefix = os.environ.get('STATSD_PREFIX', 'ranshi_kun')

# Graceful shutdown
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
worker_tmp_dir = '/dev/shm'

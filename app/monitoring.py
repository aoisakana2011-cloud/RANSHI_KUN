"""
Monitoring and logging configuration for RANSHI_KUN
"""
import os
import logging
import time
from functools import wraps
from flask import Flask, request, g
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import psutil

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_USERS = Gauge('active_users_total', 'Number of active users')
PREDICTION_ACCURACY = Gauge('prediction_accuracy', 'Current prediction accuracy')
DATABASE_CONNECTIONS = Gauge('database_connections', 'Active database connections')
CPU_USAGE = Gauge('cpu_usage_percent', 'CPU usage percentage')
MEMORY_USAGE = Gauge('memory_usage_percent', 'Memory usage percentage')

class MonitoringMiddleware:
    """Monitoring middleware for Flask application"""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize monitoring middleware"""
        self.app = app
        
        # Request monitoring
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        
        # Metrics endpoint
        @app.route('/metrics')
        def metrics():
            # Update system metrics
            self._update_system_metrics()
            return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
        
        # Health check endpoint
        @app.route('/health')
        def health():
            return {'status': 'healthy', 'timestamp': time.time()}, 200
        
        @app.route('/health/db')
        def health_db():
            try:
                from app.extensions import db
                db.engine.execute('SELECT 1')
                return {'status': 'healthy', 'database': 'connected'}, 200
            except Exception as e:
                return {'status': 'unhealthy', 'database': 'disconnected', 'error': str(e)}, 503
    
    def _before_request(self):
        """Before request handler"""
        g.start_time = time.time()
    
    def _after_request(self, response):
        """After request handler"""
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            REQUEST_DURATION.observe(duration)
        
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.endpoint or 'unknown',
            status=response.status_code
        ).inc()
        
        return response
    
    def _update_system_metrics(self):
        """Update system metrics"""
        # CPU usage
        CPU_USAGE.set(psutil.cpu_percent(interval=1))
        
        # Memory usage
        memory = psutil.virtual_memory()
        MEMORY_USAGE.set(memory.percent)
        
        # Database connections (if available)
        try:
            from app.extensions import db
            pool = db.engine.pool
            if hasattr(pool, 'size'):
                DATABASE_CONNECTIONS.set(pool.size() - pool.checkedin())
        except:
            pass

def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            app.logger.error(f"Error in {func.__name__}: {e}")
            raise
        finally:
            duration = time.time() - start_time
            app.logger.info(f"{func.__name__} executed in {duration:.3f}s")
    return wrapper

class AdvancedLogger:
    """Advanced logging configuration"""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize advanced logging"""
        self.app = app
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] - %(message)s'
        )
        
        json_formatter = JsonFormatter()
        
        # Create handlers
        handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(detailed_formatter)
        handlers.append(console_handler)
        
        # File handler for general logs
        if app.config.get('LOG_FILE'):
            file_handler = logging.handlers.RotatingFileHandler(
                app.config['LOG_FILE'],
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            file_handler.setFormatter(detailed_formatter)
            handlers.append(file_handler)
        
        # JSON file handler for structured logging
        if app.config.get('JSON_LOG_FILE'):
            json_handler = logging.handlers.RotatingFileHandler(
                app.config['JSON_LOG_FILE'],
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            json_handler.setFormatter(json_formatter)
            handlers.append(json_handler)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
        
        # Remove existing handlers and add new ones
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        for handler in handlers:
            root_logger.addHandler(handler)
        
        # Configure specific loggers
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        import json
        
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add request context if available
        if hasattr(record, 'request'):
            log_entry['request'] = {
                'method': record.request.method,
                'url': record.request.url,
                'remote_addr': record.request.remote_addr,
                'user_agent': record.request.headers.get('User-Agent')
            }
        
        return json.dumps(log_entry)

class AlertManager:
    """Alert management system"""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self.alerts = []
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize alert manager"""
        self.app = app
        
        # Setup alert checks
        app.before_request(self._check_alerts)
    
    def _check_alerts(self):
        """Check for alert conditions"""
        # High CPU usage alert
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage > 80:
            self._send_alert('high_cpu', f'CPU usage is {cpu_usage}%')
        
        # High memory usage alert
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            self._send_alert('high_memory', f'Memory usage is {memory.percent}%')
        
        # Disk space alert
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            self._send_alert('low_disk', f'Disk usage is {disk.percent}%')
    
    def _send_alert(self, alert_type, message):
        """Send alert notification"""
        alert = {
            'type': alert_type,
            'message': message,
            'timestamp': time.time(),
            'resolved': False
        }
        
        self.alerts.append(alert)
        
        # Log alert
        self.app.logger.warning(f'ALERT: {alert_type} - {message}')
        
        # Send to external monitoring service (if configured)
        if self.app.config.get('SENTRY_DSN'):
            import sentry_sdk
            sentry_sdk.capture_message(f'ALERT: {alert_type} - {message}', level='warning')

def init_monitoring(app: Flask):
    """Initialize monitoring and logging"""
    MonitoringMiddleware(app)
    AdvancedLogger(app)
    AlertManager(app)

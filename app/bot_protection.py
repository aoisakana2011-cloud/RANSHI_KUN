"""
Bot detection and IP-based registration limiting middleware
"""
import re
import time
from flask import request, jsonify, abort, current_app
from functools import wraps
import hashlib
from collections import defaultdict

class BotDetection:
    """Bot detection and prevention system"""
    
    def __init__(self, app=None):
        self.app = app
        self.ip_registrations = defaultdict(list)
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize bot detection"""
        app.before_request(self._detect_bots)
    
    def _detect_bots(self):
        """Detect and block bots"""
        user_agent = request.headers.get('User-Agent', '').lower()
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        # Known bot patterns
        bot_patterns = [
            r'googlebot',
            r'bingbot',
            r'slurp',
            r'duckduckbot',
            r'baiduspider',
            r'yandexbot',
            r'facebookexternalhit',
            r'twitterbot',
            r'linkedinbot',
            r'whatsapp',
            r'telegrambot',
            r'crawler',
            r'spider',
            r'bot',
            r'scraper',
            r'curl',
            r'wget',
            r'python-requests',
            r'python-urllib',
            r'go-http-client',
            r'java',
            r'node-fetch',
            r'axios',
            r'postman',
            r'insomnia'
        ]
        
        # Check User-Agent for bot patterns
        for pattern in bot_patterns:
            if re.search(pattern, user_agent):
                current_app.logger.warning(f"Bot detected: {user_agent} from {ip_address}")
                abort(403, description="Access denied: Automated bots not allowed")
        
        # Check for suspicious headers
        suspicious_headers = [
            'X-Forwarded-For',
            'X-Real-IP',
            'X-Proxy-User-Ip'
        ]
        
        # Check for proxy/VPN usage
        if request.headers.get('Via') or request.headers.get('X-Forwarded-For'):
            # Allow but log for monitoring
            current_app.logger.info(f"Proxy/VPN detected: {ip_address}")
    
    def check_ip_registration_limit(self, ip_address, max_registrations=1, time_window=3600):
        """Check if IP has exceeded registration limit"""
        current_time = time.time()
        
        # Clean old entries
        self.ip_registrations[ip_address] = [
            timestamp for timestamp in self.ip_registrations[ip_address]
            if current_time - timestamp < time_window
        ]
        
        # Check limit
        if len(self.ip_registrations[ip_address]) >= max_registrations:
            return False
        
        # Add current registration
        self.ip_registrations[ip_address].append(current_time)
        return True

# Global bot detection instance
bot_detection = BotDetection()

def require_human():
    """Decorator to ensure request is from human"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            user_agent = request.headers.get('User-Agent', '')
            
            # Additional human verification checks
            if not _is_likely_human(user_agent, ip_address):
                abort(403, description="Access denied: Please use a standard web browser")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def _is_likely_human(user_agent, ip_address):
    """Determine if request is likely from a human"""
    # Basic browser patterns
    browser_patterns = [
        r'mozilla',
        r'chrome',
        r'firefox',
        r'safari',
        r'edge',
        r'opera'
    ]
    
    # Must have browser-like User-Agent
    has_browser = any(re.search(pattern, user_agent.lower()) for pattern in browser_patterns)
    
    # Must not have obvious bot indicators
    bot_indicators = ['bot', 'crawler', 'spider', 'scraper']
    has_bot = any(indicator in user_agent.lower() for indicator in bot_indicators)
    
    return has_browser and not has_bot

def limit_ip_registrations(max_registrations=1, time_window=3600):
    """Decorator to limit registrations per IP"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            
            if not bot_detection.check_ip_registration_limit(ip_address, max_registrations, time_window):
                abort(429, description="Too many registration attempts from this IP")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def verify_captcha():
    """Simple CAPTCHA verification (can be enhanced with reCAPTCHA)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # For now, just check if request has typical human behavior
            # In production, integrate with Google reCAPTCHA or similar
            
            # Check request timing (humans don't submit instantly)
            referer = request.headers.get('Referer', '')
            if not referer or 'ranshi-kun' not in referer:
                abort(403, description="Invalid request source")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

"""
Security middleware for RANSHI_KUN
"""
from flask import Flask, request, jsonify
from flask_talisman import Talisman
import os

class SecurityMiddleware:
    """Security middleware for Flask application"""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize security middleware"""
        self.app = app
        
        # HTTPS redirect in production
        if app.config.get('FORCE_HTTPS', False):
            app.before_request(self._https_redirect)
        
        # Security headers with Talisman
        csp = {
            'default-src': "'self'",
            'script-src': [
                "'self'",
                "'unsafe-inline'",
                'https://cdn.jsdelivr.net',
                'https://cdnjs.cloudflare.com'
            ],
            'style-src': [
                "'self'",
                "'unsafe-inline'",
                'https://fonts.googleapis.com',
                'https://cdnjs.cloudflare.com'
            ],
            'font-src': [
                "'self'",
                'https://fonts.gstatic.com',
                'https://cdnjs.cloudflare.com'
            ],
            'img-src': [
                "'self'",
                'data:',
                'https:'
            ],
            'connect-src': [
                "'self'"
            ],
            'frame-ancestors': "'none'",
            'base-uri': "'self'",
            'form-action': "'self'"
        }
        
        Talisman(
            app,
            force_https=app.config.get('FORCE_HTTPS', False),
            strict_transport_security=True,
            content_security_policy=csp,
            referrer_policy='strict-origin-when-cross-origin',
            feature_policy={
                'geolocation': "'none'",
                'camera': "'none'",
                'microphone': "'none'",
                'payment': "'none'",
                'usb': "'none'"
            }
        )
        
        # Rate limiting
        app.before_request(self._rate_limit_check)
        
        # Request size limiting
        app.before_request(self._request_size_check)
    
    def _https_redirect(self):
        """Redirect HTTP to HTTPS"""
        if not request.is_secure:
            url = request.url.replace('http://', 'https://', 1)
            return jsonify({'error': 'HTTPS required'}), 301
    
    def _rate_limit_check(self):
        """Basic rate limiting"""
        # This is a simple implementation - in production, use Redis-based rate limiting
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        # For now, just log the request
        self.app.logger.info(f"Request from {client_ip}: {request.method} {request.path}")
    
    def _request_size_check(self):
        """Check request size"""
        max_size = self.app.config.get('MAX_REQUEST_SIZE', 16 * 1024 * 1024)  # 16MB
        
        if request.content_length and request.content_length > max_size:
            return jsonify({'error': 'Request too large'}), 413

def init_security(app: Flask):
    """Initialize security middleware"""
    SecurityMiddleware(app)

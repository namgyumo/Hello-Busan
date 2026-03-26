"""
Hello-Busan Backend Application
Flask 기반 백엔드 서버
"""

from flask import Flask, jsonify
from flask_cors import CORS
from config import Config


def create_app(config_class=Config):
    """Flask 애플리케이션 팩토리"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # CORS 설정
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 블루프린트 등록
    # from api.routes import api_bp
    # app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/')
    def index():
        return jsonify({
            "message": "Hello-Busan API Server",
            "version": "1.0.0",
            "status": "running"
        })

    @app.route('/health')
    def health_check():
        return jsonify({"status": "healthy"}), 200

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)

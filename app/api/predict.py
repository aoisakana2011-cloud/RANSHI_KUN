from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..services.prediction_advanced import add_entry_and_predict, add_entry_only

bp = Blueprint("predict", __name__)


@bp.route("/predict/<uid>", methods=["POST"])
@login_required
def predict_for_uid(uid):
    data = request.get_json() or {}
    try:
        result = add_entry_and_predict(uid, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Prediction error: {e}")  # デバッグ用
        return jsonify({"error": "prediction_failed"}), 500
    return jsonify(result)


@bp.route("/register/<uid>", methods=["POST"])
@login_required
def register_entry(uid):
    """履歴のみ登録（学習用）。予測は返さない。"""
    data = request.get_json() or {}
    try:
        result = add_entry_only(uid, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Register error: {e}")  # デバッグ用
        return jsonify({"error": "register_failed"}), 500
    return jsonify(result)


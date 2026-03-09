from flask import Blueprint, request, jsonify

from ..services.prediction import add_entry_and_predict, add_entry_only

bp = Blueprint("predict", __name__)


@bp.route("/predict/<uid>", methods=["POST"])
def predict_for_uid(uid):
    data = request.get_json() or {}
    try:
        result = add_entry_and_predict(uid, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "prediction_failed"}), 500
    return jsonify(result)


@bp.route("/register/<uid>", methods=["POST"])
def register_entry(uid):
    """履歴のみ登録（学習用）。予測は返さない。"""
    data = request.get_json() or {}
    try:
        result = add_entry_only(uid, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "register_failed"}), 500
    return jsonify(result)


"""アプリ共通のエラー型とエラーレスポンス整形（docs/api.md のエラーコード）。"""

from __future__ import annotations


class AppError(Exception):
    """API が返す業務エラー。`{"error": {"code", "message"}}` 形式に整形される。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


# docs/api.md のコード表に対応したショートカット。
def bad_image(message: str = "画像をデコードできません") -> AppError:
    return AppError(400, "bad_image", message)


def bad_request(message: str) -> AppError:
    return AppError(400, "bad_request", message)


def unauthorized(message: str = "認証が必要です") -> AppError:
    return AppError(401, "unauthorized", message)


def forbidden(message: str = "この project へのアクセス権がありません") -> AppError:
    return AppError(403, "forbidden", message)


def no_such_project(name: str) -> AppError:
    return AppError(404, "no_such_project", f"project '{name}' は存在しません")


def payload_too_large(message: str = "画像サイズが上限を超えています") -> AppError:
    return AppError(413, "payload_too_large", message)


def model_not_loaded() -> AppError:
    return AppError(503, "model_not_loaded", "埋め込みモデルが読み込まれていません")

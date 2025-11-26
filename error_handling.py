import logging
from typing import Dict, Any, Optional
from datetime import datetime,timedelta
import json

logger = logging.getLogger(__name__)


class G2AError(Exception):
    """Базовый класс для ошибок G2A API"""

    def __init__(self, message: str, error_code: str = None, http_status: int = None):
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        super().__init__(self.message)


class G2AReservationError(G2AError):
    """Ошибки резервации"""
    pass


class G2AInventoryError(G2AError):
    """Ошибки инвентаря"""
    pass


class G2AAuthError(G2AError):
    """Ошибки авторизации"""
    pass


class G2AErrorHandler:
    """Централизованный обработчик ошибок для G2A API"""

    # Коды ошибок согласно документации G2A
    ERROR_CODES = {
        # Общие ошибки
        "AUTH01": "No Authorization header",
        "AUTH02": "Merchant with this authorization not found",
        "AUTH03": "Unallowed IP address",
        "AUTH04": "No privileges to this method",
        "CTTYPE": "Bad Content-Type header in request",
        "BR01": "JSON is not valid",
        "BR02": "JSON data is not valid",
        "BR03": "Too many requests to the API",
        "WRONGURL": "Call to wrong url",
        "API00": "Something really went wrong",
        "ERR99": "Internal server error",

        # Ошибки продуктов
        "PR01": "Invalid product id",
        "PR02": "Invalid page param",
        "PR03": "Invalid min quantity params",
        "PR04": "Invalid min price from params",
        "PR05": "Invalid min price to params",

        # Ошибки заказов
        "ORD01": "Invalid order id",
        "ORD02": "Order not found",
        "ORD03": "Unable to process payment - it is not ready yet",
        "ORD04": "Order key has been downloaded already",
        "ORD05": "Payment required or it is not processed yet",
        "ORD06": "Order is not processed yet",
        "ORD110": "Unable to process payment",
        "ORD111": "Unable to find user's last transaction details",
        "ORD112": "Sorry, you don't have enough funds to pay for this order",
        "ORD113": "User doesn't exists in G2A Ecosystem",
        "ORD114": "Payment is too late. Try with another order",
        "ORD120": "Unable to process payment. Wrong payment provider's response",
        "ORD121": "You reached G2A PAY limit. Please, contact with our support",
    }

    def __init__(self):
        self.error_log = []

    def handle_http_error(self, status_code: int, response_text: str = None,
                          endpoint: str = None) -> G2AError:
        """Обработка HTTP ошибок согласно документации G2A"""

        error_info = {
            "timestamp": datetime.now().isoformat(),
            "status_code": status_code,
            "endpoint": endpoint,
            "response": response_text
        }

        if status_code == 400:
            return self._handle_bad_request(response_text, error_info)
        elif status_code == 401:
            return self._handle_unauthorized(response_text, error_info)
        elif status_code == 403:
            return self._handle_forbidden(response_text, error_info)
        elif status_code == 404:
            return self._handle_not_found(response_text, error_info)
        elif status_code == 409:
            return self._handle_conflict(response_text, error_info)
        elif status_code == 429:
            return self._handle_rate_limit(response_text, error_info)
        elif 500 <= status_code <= 599:
            return self._handle_server_error(response_text, error_info)
        else:
            return G2AError(f"Unexpected HTTP status: {status_code}", http_status=status_code)

    def _handle_bad_request(self, response_text: str, error_info: dict) -> G2AError:
        """Обработка ошибок 400 Bad Request"""
        error_code = self._extract_error_code(response_text)

        if error_code in ["BR01", "BR02"]:
            return G2AError("Invalid JSON data", error_code, 400)
        elif error_code == "BR08":
            return G2AError("Invalid GET parameters", error_code, 400)
        elif error_code in ["PR01", "PR02", "PR03", "PR04", "PR05"]:
            return G2AError("Invalid product parameters", error_code, 400)
        elif error_code == "ORD01":
            return G2AError("Invalid order ID", error_code, 400)
        else:
            return G2AError("Bad request", error_code, 400)

    def _handle_unauthorized(self, response_text: str, error_info: dict) -> G2AAuthError:
        """Обработка ошибок 401 Unauthorized"""
        error_code = self._extract_error_code(response_text)

        if error_code == "AUTH01":
            return G2AAuthError("No Authorization header", error_code, 401)
        elif error_code == "AUTH02":
            return G2AAuthError("Invalid authorization credentials", error_code, 401)
        elif error_code == "AUTH03":
            return G2AAuthError("IP address not allowed", error_code, 401)
        elif error_code == "AUTH04":
            return G2AAuthError("No privileges for this method", error_code, 401)
        else:
            return G2AAuthError("Unauthorized access", error_code, 401)

    def _handle_forbidden(self, response_text: str, error_info: dict) -> G2AError:
        """Обработка ошибок 403 Forbidden"""
        error_code = self._extract_error_code(response_text)

        if error_code == "ORD112":
            return G2AError("Insufficient funds", error_code, 403)
        elif error_code == "ORD121":
            return G2AError("G2A PAY limit reached", error_code, 403)
        else:
            return G2AError("Access forbidden", error_code, 403)

    def _handle_not_found(self, response_text: str, error_info: dict) -> G2AError:
        """Обработка ошибок 404 Not Found"""
        error_code = self._extract_error_code(response_text)

        if error_code == "ORD02":
            return G2AError("Order not found", error_code, 404)
        elif error_code == "ORD111":
            return G2AError("Transaction details not found", error_code, 404)
        elif error_code == "ORD113":
            return G2AError("User not found in G2A ecosystem", error_code, 404)
        else:
            return G2AError("Resource not found", error_code, 404)

    def _handle_conflict(self, response_text: str, error_info: dict) -> G2AError:
        """Обработка ошибок 409 Conflict"""
        return G2AError("Resource conflict", None, 409)

    def _handle_rate_limit(self, response_text: str, error_info: dict) -> G2AError:
        """Обработка ошибок 429 Too Many Requests"""
        self.error_log.append({**error_info, "type": "rate_limit"})
        return G2AError("Rate limit exceeded. Max 600 requests per minute", "BR03", 429)

    def _handle_server_error(self, response_text: str, error_info: dict) -> G2AError:
        """Обработка ошибок 5xx Server Error"""
        error_code = self._extract_error_code(response_text)

        self.error_log.append({**error_info, "type": "server_error"})

        if error_code == "API00":
            return G2AError("Critical server error", error_code, 500)
        elif error_code == "ERR99":
            return G2AError("Internal server error", error_code, 500)
        elif 500 <= int(str(error_info.get("status_code", 500))) <= 504:
            return G2AError("G2A server temporarily unavailable", error_code, 500)
        else:
            return G2AError("Server error", error_code, 500)

    def _extract_error_code(self, response_text: str) -> Optional[str]:
        """Извлечение кода ошибки из ответа G2A"""
        if not response_text:
            return None

        try:
            # Попытка парсинга JSON ответа
            if response_text.strip().startswith('{'):
                data = json.loads(response_text)
                return data.get('error', {}).get('code')
        except (json.JSONDecodeError, AttributeError):
            pass

        # Поиск кода ошибки в тексте
        for code in self.ERROR_CODES.keys():
            if code in response_text:
                return code

        return None

    def handle_reservation_timeout(self, reservation_id: str) -> G2AReservationError:
        """Обработка таймаута резервации"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "reservation_id": reservation_id,
            "type": "reservation_timeout"
        }
        self.error_log.append(error_info)

        return G2AReservationError(
            f"Reservation {reservation_id} timed out. API must respond within 9 seconds",
            "TIMEOUT_RESERVATION"
        )

    def handle_insufficient_stock(self, product_id: str, requested: int, available: int) -> G2AInventoryError:
        """Обработка недостатка товара"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "product_id": product_id,
            "requested": requested,
            "available": available,
            "type": "insufficient_stock"
        }
        self.error_log.append(error_info)

        return G2AInventoryError(
            f"Insufficient stock for product {product_id}. Requested: {requested}, Available: {available}",
            "INSUFFICIENT_STOCK"
        )

    def get_retry_strategy(self, error: G2AError) -> Dict[str, Any]:
        """Получение стратегии повтора запроса"""
        if error.error_code == "BR03":  # Rate limit
            return {
                "should_retry": True,
                "delay": 60,  # 1 минута
                "max_retries": 3
            }
        elif error.http_status and 500 <= error.http_status <= 599:  # Server errors
            return {
                "should_retry": True,
                "delay": 5,  # 5 секунд
                "max_retries": 3
            }
        elif error.error_code in ["AUTH01", "AUTH02", "AUTH04"]:  # Auth errors
            return {
                "should_retry": False,
                "message": "Check API credentials and permissions"
            }
        else:
            return {
                "should_retry": False,
                "message": "Manual intervention required"
            }

    def log_error_stats(self) -> Dict[str, Any]:
        """Статистика ошибок"""
        if not self.error_log:
            return {"total_errors": 0}

        error_types = {}
        recent_errors = []

        for error in self.error_log:
            error_type = error.get("type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1

            # Ошибки за последний час
            error_time = datetime.fromisoformat(error["timestamp"])
            if (datetime.now() - error_time).total_seconds() < 3600:
                recent_errors.append(error)

        return {
            "total_errors": len(self.error_log),
            "error_types": error_types,
            "recent_errors_count": len(recent_errors),
            "most_common_error": max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
        }

    def should_circuit_break(self, window_minutes: int = 60, threshold: int = 10) -> bool:
        """Проверка нужно ли активировать circuit breaker"""
        if len(self.error_log) < threshold:
            return False

        recent_errors = []
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)

        for error in self.error_log:
            error_time = datetime.fromisoformat(error["timestamp"])
            if error_time > cutoff_time:
                recent_errors.append(error)

        return len(recent_errors) >= threshold


# Singleton instance
error_handler = G2AErrorHandler()
"""
Кастомные исключения для G2A Automation
"""


class G2AAutomationException(Exception):
    """Базовое исключение для всего приложения"""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class G2AAPIError(G2AAutomationException):
    """Ошибки при работе с G2A API"""
    
    def __init__(self, status_code: int, message: str, response_text: str = ""):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(
            message=f"G2A API Error [{status_code}]: {message}",
            details={"status_code": status_code, "response": response_text}
        )


class AuthenticationError(G2AAPIError):
    """401 Unauthorized - проблемы с аутентификацией"""
    
    def __init__(self, message: str = "Authentication failed", response_text: str = ""):
        super().__init__(
            status_code=401,
            message=message,
            response_text=response_text
        )


class RateLimitError(G2AAPIError):
    """429 Too Many Requests - превышен лимит запросов"""
    
    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        
        super().__init__(
            status_code=429,
            message=message,
            response_text=""
        )


class TokenExpiredError(AuthenticationError):
    """Токен истёк"""
    
    def __init__(self):
        super().__init__(message="Access token expired", response_text="")


class InvalidCredentialsError(AuthenticationError):
    """Неверные credentials"""
    
    def __init__(self):
        super().__init__(
            message="Invalid G2A Client ID or Secret",
            response_text="Check your .env file"
        )


class ProductNotFoundError(G2AAPIError):
    """Продукт не найден на G2A"""
    
    def __init__(self, product_id: str):
        self.product_id = product_id
        super().__init__(
            status_code=404,
            message=f"Product {product_id} not found on G2A",
            response_text=""
        )


class OfferAlreadyExistsError(G2AAPIError):
    """Оффер уже существует"""
    
    def __init__(self, product_id: str, offer_id: str = None):
        self.product_id = product_id
        self.offer_id = offer_id
        
        message = f"Offer already exists for product {product_id}"
        if offer_id:
            message += f" (offer_id: {offer_id})"
        
        super().__init__(
            status_code=409,
            message=message,
            response_text=""
        )


class DatabaseError(G2AAutomationException):
    """Ошибки работы с базой данных"""
    pass


class KeyNotFoundError(DatabaseError):
    """Ключ не найден в БД"""
    
    def __init__(self, key_id: int = None, game_name: str = None):
        if key_id:
            message = f"Key with ID {key_id} not found"
        elif game_name:
            message = f"No keys found for game '{game_name}'"
        else:
            message = "Key not found"
        
        super().__init__(message=message)


class PriceParsingError(G2AAutomationException):
    """Ошибки парсинга цен"""
    
    def __init__(self, game_name: str, reason: str):
        super().__init__(
            message=f"Failed to parse price for '{game_name}': {reason}",
            details={"game": game_name, "reason": reason}
        )


class ConfigurationError(G2AAutomationException):
    """Ошибки конфигурации"""
    
    def __init__(self, message: str):
        super().__init__(message=f"Configuration error: {message}")


def is_retryable_error(exception: Exception) -> bool:
    """
    Определяет, можно ли повторить запрос после этой ошибки
    
    Args:
        exception: Исключение для проверки
        
    Returns:
        True если ошибка временная и можно повторить
    """
    # Временные сетевые ошибки
    if isinstance(exception, (TimeoutError, ConnectionError)):
        return True
    
    # Rate limit - можно повторить после паузы
    if isinstance(exception, RateLimitError):
        return True
    
    # Истекший токен - можно обновить и повторить
    if isinstance(exception, TokenExpiredError):
        return True
    
    # 5xx ошибки сервера - можно повторить
    if isinstance(exception, G2AAPIError) and 500 <= exception.status_code < 600:
        return True
    
    return False


if __name__ == "__main__":
    # Тестирование
    try:
        raise AuthenticationError("Test auth error")
    except G2AAutomationException as e:
        print(f"Caught: {e}")
        print(f"Details: {e.details}")

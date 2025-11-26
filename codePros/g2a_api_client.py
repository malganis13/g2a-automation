import asyncio
import hashlib
import json
import httpx
import g2a_config
from g2a_config import REQUEST_TIMEOUT, G2A_API_BASE
from proxy_manager import ProxyManager
from color_utils import print_success, print_error, print_warning, print_info
import functools


def handle_api_exception(e):
    """Вспомогательная функция для обработки исключений API"""
    if ("401" in str(e) or "unauthorized" in str(e).lower()):
        raise e
    return {
        "success": False,
        "error": str(e)
    }


def auto_refresh_token(func):
    """Декоратор для автоматического обновления токена при ошибке 401"""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            if ("401" in error_str or
                    "unauthorized" in error_str or
                    ("token" in error_str and ("expired" in error_str or "invalid" in error_str))):

                print_warning("🔄 Токен истек, обновляем и повторяем запрос...")
                try:
                    await self.get_token()
                    print_info("✓ Токен обновлен, повторяем запрос...")
                    return await func(self, *args, **kwargs)
                except Exception as token_error:
                    print_error(f"❌ Ошибка обновления токена: {token_error}")
                    raise e
            else:
                raise e

    return wrapper


class G2AApiClient:
    def __init__(self):
        self.token = None
        self.rate = 1.1  # Дефолтный курс
        self.proxy_manager = ProxyManager()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass  # httpx клиенты закрываются автоматически через async with

    async def get_token(self):
        """Получение OAuth токена для G2A API (с httpx)"""
        g2a_config.reload_config()

        client_id = g2a_config.G2A_CLIENT_ID
        client_secret = g2a_config.G2A_CLIENT_SECRET
        api_base = g2a_config.G2A_API_BASE

        print(f"DEBUG: Получение токена G2A...")
        print(f"DEBUG: Client ID: {client_id[:10] if client_id else 'ПУСТО'}... (длина: {len(client_id)})")
        print(f"DEBUG: Secret: {client_secret[:10] if client_secret else 'ПУСТО'}... (длина: {len(client_secret)})")

        if not client_id or not client_secret:
            raise Exception(
                "❌ G2A Client ID или Secret пусты!\n\n"
                "Заполните в GUI:\n"
                "⚙️ Настройки → G2A API → Сохранить"
            )

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.post(
                f"{api_base}/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
            )

            if response.status_code == 200:
                self.token = response.json()["access_token"]
                print(f"✅ Токен получен успешно!")
            else:
                error_msg = f"Token error: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)

    async def get_rate(self):
        """Получение курса EUR/USD"""
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                response = await client.get("https://api.exchangerate-api.com/v4/latest/EUR")
                if response.status_code == 200:
                    self.rate = response.json()["rates"]["USD"]
                    print(f"✅ Курс EUR/USD: {self.rate}")
                else:
                    self.rate = 1.1
                    print(f"⚠️  Не удалось получить курс, используем дефолтный: {self.rate}")
        except Exception as e:
            self.rate = 1.1
            print(f"⚠️  Ошибка получения курса ({e}), используем дефолтный: {self.rate}")

    def is_auth_error(self, status_code, response_text=""):
        """Проверка, является ли ошибка связанной с авторизацией"""
        if status_code == 401:
            return True

        response_lower = response_text.lower()
        auth_keywords = ["unauthorized", "invalid token", "token expired", "authentication failed"]
        return any(keyword in response_lower for keyword in auth_keywords)

    @auto_refresh_token
    async def get_offers(self):
        """Получение списка офферов (с httpx)"""
        if not self.token:
            raise Exception("No token available")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        all_offers = {}
        page = 1

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            while True:
                response = await client.get(
                    f"{G2A_API_BASE}/v3/sales/offers",
                    headers=headers,
                    params={
                        "itemsPerPage": 100,
                        "page": page
                    }
                )

                if response.status_code != 200:
                    if self.is_auth_error(response.status_code, response.text):
                        raise Exception(f"401 Unauthorized: {response.text}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }

                data = response.json()
                offers_data = data.get("data", [])
                meta = data.get("meta", {})

                for offer in offers_data:
                    product_id = str(offer.get("product", {}).get("id"))
                    if product_id and product_id != "None":
                        all_offers[product_id] = {
                            "id": offer.get("id"),
                            "product_name": offer.get("product", {}).get("name", f"ID: {product_id}"),
                            "price": offer.get("price", "N/A"),
                            "current_stock": offer.get("inventory", {}).get("size", 0),
                            "is_active": offer.get("status") == "active",
                            "offer_type": offer.get("type", "game")
                        }

                total_results = meta.get("totalResults", 0)
                items_per_page = meta.get("itemsPerPage", 100)
                current_page = meta.get("page", 1)

                if current_page * items_per_page >= total_results:
                    break

                page += 1

        return {
            "success": True,
            "offers_cache": all_offers,
            "total_loaded": len(all_offers)
        }


    def is_auth_error(self, status_code, response_text=""):
        """Проверка, является ли ошибка связанной с авторизацией"""
        if status_code == 401:
            return True

        response_lower = response_text.lower()
        auth_keywords = ["unauthorized", "invalid token", "token expired", "authentication failed"]
        return any(keyword in response_lower for keyword in auth_keywords)

    @auto_refresh_token
    async def get_product_price(self, product_id):
        """Получение цены продукта с minPrice и retailMinBasePrice (с httpx)"""
        if not self.token:
            raise Exception("No token available")

        url = f"{G2A_API_BASE}/v1/products"
        params = {
            "id": product_id,
            "includeOutOfStock": "true"
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                    response = await client.get(url, params=params, headers=headers)

                    if response.status_code == 429:
                        print(f"Rate limited on API, waiting...")
                        await asyncio.sleep(2)
                        continue

                    if response.status_code != 200:
                        if self.is_auth_error(response.status_code, response.text):
                            raise Exception(f"401 Unauthorized: {response.text}")
                        print(f"API HTTP {response.status_code} for product {product_id}")
                        return None

                    data = response.json()
                    products = data.get("docs", [])

                    if not products:
                        print(f"Не найдена игра по ID {product_id}")
                        return None

                    product = products[0]

                    min_price = product.get("minPrice")
                    retail_min_base_price = product.get("retailMinBasePrice")

                    if min_price is not None and retail_min_base_price is not None:
                        usd_price = float(min_price) * self.rate
                        return {
                            "min_price": float(min_price),
                            "min_price_usd": usd_price,
                            "retail_price": float(retail_min_base_price)
                        }
                    else:
                        print(f"Не найдена цена для {product_id}")
                        return None

            except Exception as e:
                error_str = str(e)
                if "401" in error_str or "unauthorized" in error_str.lower():
                    raise e

                print(f"Error getting price for {product_id} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return None

        return None

    @auto_refresh_token
    async def create_offer(self, product_id: str, price: float, quantity: int = 1, currency: str = "EUR",
                           restrictions=None):
        """Создание оффера (с httpx)"""
        if not self.token:
            raise Exception("No token available")

        if price <= 5:
            price = price * 0.97
        elif price > 5:
            price = price * 0.99
        price = round(price, 2)

        variant = {
            "productId": product_id,
            "price": {
                "retail": str(price),
                "business": str(price)
            },
            "inventory": {
                "size": quantity
            },
            "active": True,
            "visibility": "all",
            "regions": ["GLOBAL"]
        }

        if restrictions:
            has_include = "include" in restrictions and restrictions["include"]
            has_exclude = "exclude" in restrictions and restrictions["exclude"]

            if has_include or has_exclude:
                variant["regionRestrictions"] = restrictions

        data = {
            "offerType": "dropshipping",
            "variants": [variant]
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.post(
                    f"{G2A_API_BASE}/v3/sales/offers",
                    json=data,
                    headers=headers
                )

                if response.status_code in [200, 201, 202]:
                    result = response.json()
                    job_id = result.get("data", {}).get("jobId") if "data" in result else result.get("jobId")
                    return {
                        "success": True,
                        "data": result,
                        "job_id": job_id,
                        "message": f"Оффер создан успешно для продукта {product_id}. Job ID: {job_id}"
                    }
                else:
                    error_text = response.text
                    if self.is_auth_error(response.status_code, error_text):
                        raise Exception(f"401 Unauthorized: {error_text}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {error_text}",
                        "message": "Ошибка создания оффера"
                    }
        except Exception as e:
            if ("401" in str(e) or "unauthorized" in str(e).lower()):
                raise e
            return {
                "success": False,
                "error": str(e),
                "message": "Ошибка создания оффера"
            }

    @auto_refresh_token
    async def check_job_status_simple(self, job_id: str):
        """Проверка статуса задачи (с httpx)"""
        if not self.token:
            raise Exception("No token available")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.get(
                    f"{G2A_API_BASE}/v3/jobs/{job_id}",
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    job_data = data.get("data", {})

                    return {
                        "success": True,
                        "status": job_data.get("status"),
                        "elements": job_data.get("elements", [])
                    }
                else:
                    if self.is_auth_error(response.status_code, response.text):
                        raise Exception(f"401 Unauthorized: {response.text}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return handle_api_exception(e)

    async def create_new_offer_with_fallback(self, game_name, product_id, price, offers_cache, restrictions=None):
        try:
            create_result = await self.create_offer(
                product_id=str(product_id),
                price=price,
                quantity=1,
                restrictions=restrictions
            )

            if create_result["success"]:
                job_id = create_result.get("job_id")
                if job_id:
                    print(f"Оффер создается... Job ID: {job_id}")
                    await asyncio.sleep(4)

                    status_result = await self.check_job_status_simple(job_id)
                    if (status_result.get("success") and
                            status_result.get("status") == "complete"):

                        elements = status_result.get("elements", [])
                        if elements and elements[0].get("status") == "completed":
                            real_offer_id = elements[0].get("resourceId")

                            if real_offer_id:
                                offers_cache[str(product_id)] = {
                                    "id": real_offer_id,
                                    "current_stock": 1,
                                    "is_active": True
                                }
                                print_success(f"✅ Игра {game_name} успешно выставлена на продажу за €{price:.2f}")
                                return True
                            else:
                                print_error(f"❌ Не найден resourceId в elements")
                                return False
                        else:
                            print_error(f"❌ Элемент не completed или elements пустой")
                            return False
                    else:
                        print_error(f"❌ Job не завершен успешно: {status_result}")
                        return False
                else:
                    print_error(f"❌ Не получен job_id")
                    return False
            else:
                error_msg = create_result.get('error', '')

                if "409" in str(error_msg) or "already exists" in str(error_msg).lower():
                    print(f"🔍 Оффер уже существует для {product_id}")

                    existing_offer_id = self.extract_offer_id_from_error(error_msg)

                    if existing_offer_id:
                        print(f"📋 Найден offerId в ошибке: {existing_offer_id}")

                        offer_details = await self.get_offer_details(existing_offer_id)

                        if offer_details.get("success"):
                            offer_data = offer_details.get("data", {})
                            current_stock = self.extract_current_stock_from_offer(offer_data)
                            is_active = self.extract_active_status_from_offer(offer_data)

                            offers_cache[str(product_id)] = {
                                "id": existing_offer_id,
                                "current_stock": current_stock,
                                "is_active": is_active
                            }

                            new_stock = current_stock + 1
                            success = await self.update_offer_stock_and_activate(
                                existing_offer_id, new_stock
                            )

                            if success:
                                offers_cache[str(product_id)]['current_stock'] = new_stock
                                offers_cache[str(product_id)]['is_active'] = True

                                status_text = "активирован" if not is_active else "обновлен"
                                print_success(
                                    f"✅ Оффер {status_text} для {game_name}: stock {current_stock} → {new_stock}")
                                return True
                            else:
                                print_error(f"❌ Не удалось обновить существующий оффер")
                                return False
                        else:
                            print_error(f"❌ Не удалось получить детали оффера {existing_offer_id}")
                            return False
                    else:
                        print_error(f"❌ Не удалось извлечь offerId из ошибки: {error_msg}")
                        return False
                else:
                    print_error(f"❌ Другая ошибка создания оффера: {error_msg}")
                    return False

        except Exception as e:
            print(f"Ошибка создания оффера: {e}")
            return False

    def extract_offer_id_from_error(self, error_msg):
        try:
            import re
            if isinstance(error_msg, str):
                json_match = re.search(r'\{.*\}', error_msg)
                if json_match:
                    error_json = json.loads(json_match.group())

                    if "data" in error_json and "offerId" in error_json["data"]:
                        return error_json["data"]["offerId"]
                    if "offerId" in error_json:
                        return error_json["offerId"]
            return None
        except Exception as e:
            print(f"Ошибка извлечения offerId: {e}")
            return None

    def extract_current_stock_from_offer(self, offer_data):
        try:
            variants = offer_data.get("variants", [])
            if variants:
                inventory = variants[0].get("inventory", {})
                return inventory.get("size", 0)
            return 0
        except Exception:
            return 0

    def extract_active_status_from_offer(self, offer_data):
        try:
            variants = offer_data.get("variants", [])
            if variants:
                return variants[0].get("active", False)
            return False
        except Exception:
            return False

    async def update_offer_stock_and_activate(self, offer_id, new_quantity):
        try:
            update_data = {
                "offerType": "dropshipping",
                "variant": {
                    "inventory": {
                        "size": new_quantity
                    },
                    "active": True
                }
            }

            result = await self.update_offer_partial(offer_id, update_data)
            return result.get("success", False)
        except Exception as e:
            print(f"Ошибка обновления оффера: {e}")
            return False

    @auto_refresh_token
    async def update_offer_partial(self, offer_id: str, update_data: dict):
        """Частичное обновление оффера (PATCH запрос с httpx)"""
        if not self.token:
            raise Exception("No token available")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.patch(
                f"{G2A_API_BASE}/v3/sales/offers/{offer_id}",
                json=update_data,
                headers=headers
            )

            if response.status_code in [200, 202]:
                return {
                    "success": True,
                    "data": response.json() if response.status_code == 200 else {},
                    "message": f"Оффер {offer_id} обновлен"
                }
            else:
                if self.is_auth_error(response.status_code, response.text):
                    raise Exception(f"401 Unauthorized: {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }

    @auto_refresh_token
    async def get_offer_details(self, offer_id):
        """Получение деталей конкретного оффера по ID (с httpx)"""
        if not self.token:
            raise Exception("No token available")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.get(
                    f"{G2A_API_BASE}/v3/sales/offers/{offer_id}",
                    headers=headers
                )

                if response.status_code == 200:
                    return {
                        "success": True,
                        "data": response.json()
                    }
                elif response.status_code == 404:
                    return {
                        "success": False,
                        "error": f"Оффер {offer_id} не найден"
                    }
                elif response.status_code == 401:
                    await self.get_token()
                    print('получен новый токен, пробуем еще раз')
                    return await self.get_offer_details(offer_id)
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @auto_refresh_token
    async def delete_offer(self, offer_id: str):
        """Удаление офера (с httpx)"""
        if not self.token:
            raise Exception("No token available")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.delete(
                    f"{G2A_API_BASE}/v3/sales/offers/{offer_id}",
                    headers=headers
                )

                if response.status_code in [200, 204]:
                    return {
                        "success": True,
                        "message": f"Офер {offer_id} удален"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
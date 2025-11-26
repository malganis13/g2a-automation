from curl_cffi.requests import AsyncSession
import asyncio
import json
from urllib.parse import quote
from g2a_config import G2A_BASE_URL, G2A_BASE_PARAMS, REGION_CODES, HEADERS, REQUEST_TIMEOUT, DELAY_BETWEEN_REQUESTS


class G2AIdParser:
    def __init__(self, proxy_manager):
        self.proxy_manager = proxy_manager
        self.session = None
        self.count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search_game_id(self, game_name, region="GLOBAL"):
        region_code = REGION_CODES.get(region, REGION_CODES["GLOBAL"])
        query = quote(game_name)
        url = f"{G2A_BASE_URL}?{G2A_BASE_PARAMS}&f%5Bregion%5D%5B0%5D={region_code}&query={query}"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.count += 1
                proxy = self.proxy_manager.get_current_proxy()
                proxies = {"http": proxy, "https": proxy} if proxy else None

                if not self.session or self.count == 13:
                    self.session = AsyncSession(
                        headers=HEADERS,
                        timeout=REQUEST_TIMEOUT,
                        proxies=proxies,
                        impersonate="chrome120",
                        verify=False
                    )
                    self.count = 0
                print(f"Получаем G2A ID для: {game_name} (регион: {region})")
                response = await self.session.get(url)

                if response.status_code == 429:
                    print(f"Rate limited, rotating proxy and retrying...")
                    await asyncio.sleep(2)
                    continue

                if response.status_code != 200:
                    print(f"HTTP {response.status_code} for {game_name}")
                    return None

                g2a_id = self.extract_id_from_html(response.text, game_name)
                return g2a_id

            except Exception as e:
                print(f"Error searching {game_name} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return None

        return None

    def normalize_name(self, name):
        """Нормализация названия для сравнения - убираем технические слова но сохраняем структуру"""
        name = name.lower()
        # Убираем технические слова в любом месте строки
        name = name.replace("steam key", "").replace("steam", "")
        name = name.replace("key", "")
        name = name.replace("(pc)", "").replace("pc", "")
        name = name.replace("global", "").replace("europe", "").replace("eu", "")
        name = name.replace("north america", "").replace("latam", "").replace("asia", "")
        # Убираем лишние пробелы
        name = " ".join(name.split())
        return name.strip()

    def extract_id_from_html(self, html, game_name):
        try:
            start = html.find('"items":[')
            if start == -1:
                print("Items block not found")
                return None

            i = start + len('"items":')
            bracket_level = 0
            result = ""

            for ch in html[i:]:
                result += ch
                if ch == "[":
                    bracket_level += 1
                elif ch == "]":
                    bracket_level -= 1
                    if bracket_level == 0:
                        break

            items = json.loads(result)

            # Нормализуем искомое название
            game_normalized = self.normalize_name(game_name)

            best_match = None
            best_match_length = float('inf')

            for product in items:
                name = product.get("name", "")
                name_lower = name.lower()

                if "random" in name_lower:
                    continue

                # Нормализуем название продукта
                product_normalized = self.normalize_name(name)

                # Проверяем точное совпадение после нормализации
                if game_normalized == product_normalized:
                    product_id = product.get("meta", {}).get("productId", "")
                    if product_id:
                        clean_id = product_id[1:] if product_id.startswith("i") else product_id
                        print(f"✓ Точное совпадение: {name}")
                        return clean_id

                # Проверяем полное вхождение искомой строки в название продукта
                if game_normalized in product_normalized:
                    # Выбираем продукт с самым коротким названием (наиболее точное совпадение)
                    if len(product_normalized) < best_match_length:
                        best_match_length = len(product_normalized)
                        best_match = product

            # Если нашли совпадение по вхождению
            if best_match:
                product_id = best_match.get("meta", {}).get("productId", "")
                if product_id:
                    clean_id = product_id[1:] if product_id.startswith("i") else product_id
                    print(f"✓ Найдено вхождение '{game_normalized}' в: {best_match.get('name', '')}")
                    return clean_id

            print(f"❌ Игра '{game_name}' не найдена после проверки {len(items)} результатов")
            print(f"   Искали: '{game_normalized}'")
            if items:
                print(f"   Первый результат был: '{self.normalize_name(items[0].get('name', ''))}'")
            return None

        except Exception as e:
            print(f"Error parsing HTML for {game_name}: {e}")
            return None
from g2a_config import COUNTRY_TO_REGION
from collections import Counter


class RegionAnalyzer:
    def __init__(self):
        pass

    def analyze_key_region(self, line_parts):
        # Формат: Game | key | Restrictions
        # Или: €price | Game | key | Restrictions (индекс 3)
        # Или: selling | €price | Game | key | Restrictions (индекс 4)

        if len(line_parts) >= 5 and line_parts[0].startswith('selling'):
            # selling | €price | Game | key | Restrictions
            restrictions = line_parts[4].strip()
        elif len(line_parts) >= 4 and '€' in line_parts[0]:
            # €price | Game | key | Restrictions
            restrictions = line_parts[3].strip()
        elif len(line_parts) >= 3:
            # Game | key | Restrictions
            restrictions = line_parts[2].strip()
        else:
            return "GLOBAL"

        # Обработка "All except:" или "Disallowed:"
        if restrictions.startswith("All except") or restrictions.startswith("Disallowed:"):
            return "GLOBAL"

        # Обработка "Only:" или "Exclusive:"
        if restrictions.startswith("Only:"):
            countries_str = restrictions.replace("Only:", "").strip()
            countries = [c.strip() for c in countries_str.split(",")]
            return self.determine_region_by_countries(countries)

        if restrictions.startswith("Exclusive:"):
            countries_str = restrictions.replace("Exclusive:", "").strip()
            countries = [c.strip() for c in countries_str.split(",")]
            return self.determine_region_by_countries(countries)

        return "GLOBAL"

    def parse_restrictions_for_g2a(self, line_parts):
        # Формат: Game | key | Restrictions
        # Или: €price | Game | key | Restrictions (индекс 3)
        # Или: selling | €price | Game | key | Restrictions (индекс 4)

        if len(line_parts) >= 5 and line_parts[0].startswith('selling'):
            # selling | €price | Game | key | Restrictions
            restrictions_text = line_parts[4].strip()
        elif len(line_parts) >= 4 and '€' in line_parts[0]:
            # €price | Game | key | Restrictions
            restrictions_text = line_parts[3].strip()
        elif len(line_parts) >= 3:
            # Game | key | Restrictions
            restrictions_text = line_parts[2].strip()
        else:
            return None

        if not restrictions_text:
            return None

        # Обработка "All except:" или "Disallowed:"
        if restrictions_text.startswith("All except:"):
            countries_str = restrictions_text.replace("All except:", "").strip()
            excluded_countries = [c.strip() for c in countries_str.split(",") if c.strip()]

            if excluded_countries:
                return {
                    "exclude": excluded_countries
                }
            return None

        elif restrictions_text.startswith("Disallowed:"):
            countries_str = restrictions_text.replace("Disallowed:", "").strip()
            excluded_countries = [c.strip() for c in countries_str.split(",") if c.strip()]

            if excluded_countries:
                return {
                    "exclude": excluded_countries
                }
            return None

        # Обработка "Only:" или "Exclusive:"
        elif restrictions_text.startswith("Only:"):
            countries_str = restrictions_text.replace("Only:", "").strip()
            included_countries = [c.strip() for c in countries_str.split(",") if c.strip()]

            if included_countries:
                return {
                    "include": included_countries
                }
            return None

        elif restrictions_text.startswith("Exclusive:"):
            countries_str = restrictions_text.replace("Exclusive:", "").strip()
            included_countries = [c.strip() for c in countries_str.split(",") if c.strip()]

            if included_countries:
                return {
                    "include": included_countries
                }
            return None

        return None

    def determine_region_by_countries(self, countries):
        region_counts = Counter()

        for country in countries:
            if country in COUNTRY_TO_REGION:
                region = COUNTRY_TO_REGION[country]
                region_counts[region] += 1

        if not region_counts:
            return "GLOBAL"

        sorted_regions = region_counts.most_common()
        primary_region = sorted_regions[0][0]

        return primary_region

    def get_search_regions_priority(self, target_region):
        if target_region == "GLOBAL":
            return ["GLOBAL"]

        priorities = {
            "EUROPE": ["EUROPE", "GLOBAL", "NORTH_AMERICA", "ASIA", "LATAM"],
            "NORTH_AMERICA": ["NORTH_AMERICA", "GLOBAL", "EUROPE", "LATAM", "ASIA"],
            "ASIA": ["ASIA", "GLOBAL", "EUROPE", "NORTH_AMERICA", "LATAM"],
            "LATAM": ["LATAM", "GLOBAL", "NORTH_AMERICA", "EUROPE", "ASIA"]
        }

        return priorities.get(target_region, ["GLOBAL"])


    def get_restriction_description(self, restrictions):
        if not restrictions:
            return "GLOBAL (без ограничений)"

        if "include" in restrictions:
            countries_count = len(restrictions["include"])
            return f"Only {countries_count} countries: {', '.join(restrictions['include'][:5])}{'...' if countries_count > 5 else ''}"

        if "exclude" in restrictions:
            countries_count = len(restrictions["exclude"])
            return f"All except {countries_count} countries: {', '.join(restrictions['exclude'][:5])}{'...' if countries_count > 5 else ''}"

        return "Unknown restriction format"

    def validate_restrictions(self, restrictions):
        if not restrictions:
            return True, None

        has_include = "include" in restrictions and restrictions["include"]
        has_exclude = "exclude" in restrictions and restrictions["exclude"]

        if has_include and has_exclude:
            return False, "Cannot have both include and exclude restrictions"

        if not has_include and not has_exclude:
            return False, "Empty restrictions object"

        all_countries = []
        if has_include:
            all_countries.extend(restrictions["include"])
        if has_exclude:
            all_countries.extend(restrictions["exclude"])

        for country in all_countries:
            if not country or len(country) != 2 or not country.isalpha():
                return False, f"Invalid country code: {country}"

        return True, None
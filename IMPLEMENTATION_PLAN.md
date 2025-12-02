# 🎯 Implementation Plan: Smart Auto-Pricing Feature

## 📋 Overview

This document describes the complete implementation of the smart auto-pricing system with individual product thresholds and competitor tracking.

---

## ✅ Completed Changes

### 1. **Database Schema** (`database.py`)

#### New Tables:

```sql
CREATE TABLE product_settings (
    product_id TEXT PRIMARY KEY,
    game_name TEXT,
    min_floor_price REAL,          -- 🔒 Minimum price threshold per product
    undercut_amount REAL DEFAULT 0.01,  -- Amount to undercut competitor
    auto_enabled INTEGER DEFAULT 0,     -- Auto-pricing enabled (0/1)
    updated_at TEXT
);

CREATE TABLE price_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT,
    game_name TEXT,
    old_price REAL,
    new_price REAL,
    market_price REAL,
    change_amount REAL,
    change_reason TEXT,
    created_at TEXT
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    product_id TEXT,
    product_name TEXT,
    price REAL,
    quantity INTEGER DEFAULT 1,
    customer_id TEXT,
    status TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

#### New Methods:
- `get_product_settings(product_id)` - Get individual product settings
- `set_product_settings(...)` - Set min price, auto-enabled, etc.
- `get_all_product_settings()` - Get all product settings
- `save_price_change(...)` - Log price changes to DB (instead of JSON)
- `get_price_changes_stats(days)` - Get statistics for 1/7/30 days
- `save_order(...)` - Save order/sale to DB
- `get_sales_stats(days)` - Get sales statistics

---

## 🛠️ Pending Changes

### 2. **G2A API Client** (`g2a_api_client.py`)

#### New Method:
```python
async def get_competitor_min_price(self, product_id, my_seller_id):
    """
    Get minimum competitor price for a product.
    
    Uses: GET /v3/products/{productId}/offers
    
    Filters:
    - Active offers only
    - Exclude my_seller_id
    - Sort by price ASC
    - Return first result
    
    Returns:
        {
            "success": True,
            "competitor_price": 5.99,
            "competitor_seller_id": "xxx",
            "total_competitors": 12
        }
    """
```

---

### 3. **Auto Price Changer** (`auto_price_changer.py`)

#### Updated Logic:

```python
async def adjust_price_for_offer(offer_id, product_id):
    # 1. Get my current price
    my_price = await api.get_offer_price(offer_id)
    
    # 2. Get competitor min price from API
    competitor_data = await api.get_competitor_min_price(product_id, my_seller_id)
    competitor_price = competitor_data["competitor_price"]
    
    # 3. Get product settings from DB
    settings = db.get_product_settings(product_id)
    
    if not settings:
        # No settings = skip (auto not enabled)
        return
    
    if settings["auto_enabled"] != 1:
        # Auto disabled for this product
        return
    
    min_floor = settings.get("min_floor_price") or 0.1
    undercut = settings.get("undercut_amount") or 0.01
    
    # 4. Calculate target price
    target_price = competitor_price - undercut
    
    # 5. Apply floor threshold logic
    if target_price < min_floor:
        # 🛑 Competitor too cheap, stop at floor
        new_price = min_floor
        reason = f"🛑 Floor reached (competitor: €{competitor_price:.2f}, floor: €{min_floor:.2f})"
        
        # Send Telegram notification
        await telegram.send(
            f"⚠️ {game_name}\n"
            f"👥 Competitor: €{competitor_price:.2f}\n"
            f"🛑 Your floor: €{min_floor:.2f}\n"
            f"🔴 Auto-pricing stopped"
        )
    else:
        # ✅ Normal undercut
        new_price = target_price
        reason = f"✅ Undercut by €{undercut:.2f} (competitor: €{competitor_price:.2f})"
    
    # 6. Update price if changed
    if abs(new_price - my_price) >= 0.01:
        result = await api.update_offer_price(offer_id, new_price)
        
        if result["success"]:
            # Log to DB
            db.save_price_change(
                product_id=product_id,
                old_price=my_price,
                new_price=new_price,
                market_price=competitor_price,
                reason=reason,
                game_name=game_name
            )
            
            print(f"✅ {game_name}: €{my_price:.2f} → €{new_price:.2f}")
```

---

### 4. **GUI Refactoring** (`g2a_gui.py`)

#### Changes:

1. **Merge Tabs**: Remove "🎮 Offers" tab, merge all functionality into "🤖 Auto-pricing"

2. **New Table Columns**:
```
| ☑ | ID | Game | My Price | Competitor | Floor | Auto | Actions |
|---|----|----|---------|-----------|-------|------|--------|
| ☑ | abc | Game 1 | €5.99 | €6.50 | €4.00 | 🟢 | [...] |
```

3. **Offer Selection Panel**:
```
🎮 Game: Cyberpunk 2077
💰 My Price: €5.99
🏆 Competitor (min): €6.50
📉 Difference: +€0.51 (you're cheaper)
🛑 Floor: €4.00
🤖 Auto: 🟢 ENABLED
```

4. **New Buttons**:
- `[🔄 Refresh Competitor Price]` - Fetch latest competitor price
- `[💰 Set My Price]` - Manual price change
- `[🛑 Set Floor Price]` - Set minimum threshold
- `[🤖 Toggle Auto]` - Enable/disable auto for this product
- `[☑ Enable Auto for Selected]` - Batch enable
- `[🛑 Set Floor for Selected]` - Batch set floor

---

### 5. **Statistics Tab Update** (`g2a_gui.py`)

#### New Stats Display:

```
════════════════════════════════════
📈 PRICE CHANGES STATISTICS - Last 7 Days
════════════════════════════════════

Total Changes: 145
📉 Price Decreases: 120
📈 Price Increases: 25
💰 Avg Change: -€0.15
🔴 Floors Hit: 8 products

TOP CHANGED PRODUCTS:
1. Cyberpunk 2077 - 23 changes
2. GTA V - 18 changes
...

════════════════════════════════════
📈 SALES STATISTICS - Last 7 Days
════════════════════════════════════

Total Sales: 48
💰 Revenue: €287.52
📉 Avg Price: €5.99

TOP SELLING:
1. Cyberpunk 2077 - 12 sales - €71.88
2. GTA V - 8 sales - €47.92
...
```

---

### 6. **Telegram Notifications** (`telegram_notifier.py`)

#### Updated Messages:

**Price Change**:
```
📉 PRICE CHANGED
🎮 Cyberpunk 2077
€5.99 → €5.49
👥 Competitor: €5.50
✅ Undercut by €0.01
```

**Floor Reached**:
```
⚠️ FLOOR REACHED
🎮 Cyberpunk 2077
👥 Competitor: €3.50
🛑 Your floor: €4.00
🔴 Auto-pricing stopped
👉 Adjust floor or wait for competitor to raise price
```

**Sale**:
```
🎉 SALE!
🎮 Cyberpunk 2077
💰 €5.99
📈 Revenue: €5.99
```

---

## 🛣️ Implementation Order

- [x] 1. Database schema (DONE)
- [ ] 2. G2A API client - competitor price method
- [ ] 3. Auto price changer - new logic with floors
- [ ] 4. GUI refactoring - merge tabs
- [ ] 5. Statistics tab updates
- [ ] 6. Telegram notifications
- [ ] 7. Testing

---

## 📝 Notes

### Key Principles:

1. **No Conflicts**: Point-enabled and mass-enabled offers use the same `auto_enabled` flag in DB
2. **Individual Control**: Each product has its own floor price in `product_settings` table
3. **API-Based**: Competitor prices come from G2A API (no web scraping)
4. **Persistent Stats**: All changes saved to DB, statistics survive restarts
5. **Smart Notifications**: Different messages for price changes vs sales

### Floor Logic:

```
IF competitor_price - 0.01 >= my_floor:
    my_price = competitor_price - 0.01  # ✅ Normal undercut
ELSE:
    my_price = my_floor  # 🛑 Stop at floor, don't go lower
    send_telegram_alert()
```

---

**Status**: 🟡 IN PROGRESS
**Branch**: `feature/smart-auto-pricing`
**Last Updated**: 2025-12-02
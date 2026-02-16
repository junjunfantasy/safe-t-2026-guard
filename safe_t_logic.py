import datetime
import re
import os
import dotenv  # 加载环境变量，适配敏感信息管理

# 加载.env文件中的环境变量（如Gemini API Key）
dotenv.load_dotenv()

def check_order_id_format(order_id):
    """
    亚马逊订单ID格式校验：xxx-xxxx-xxx
    适配亚马逊官方订单ID规则，避免无效输入
    :param order_id: 待校验的订单ID字符串
    :return: bool - 格式正确返回True，否则False
    """
    if not order_id:
        return False
    order_id_reg = re.compile(r'^\d{3}-\d{4}-\d{3}$')
    return bool(order_id_reg.match(order_id))

def check_safet_deadline(order_date_str):
    """
    核心逻辑：校验SAFE-T索赔截止时间（适配2026年30天新政）
    优化点：UTC时间校准、精确到天+小时、返回结构化结果
    :param order_date_str: 订单日期字符串（格式：YYYY-MM-DD）
    :return: dict - 包含状态、剩余时间、提示语等结构化结果
    """
    # 1. 基础校验：订单日期格式
    try:
        order_date = datetime.datetime.strptime(order_date_str, "%Y-%m-%d")
    except ValueError:
        return {
            "status": "ERROR",
            "message": "❌ 订单日期格式错误！请输入 YYYY-MM-DD 格式",
            "days_left": 0,
            "hours_left": 0,
            "time_left_str": "",
            "color": "orange"
        }

    # 2. UTC时间校准（核心优化：贴合亚马逊全球服务器时区）
    now = datetime.datetime.utcnow()
    utc_order_date = datetime.datetime.utcnow().replace(
        year=order_date.year,
        month=order_date.month,
        day=order_date.day,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )
    # 计算索赔截止日期（30天新政）
    deadline = utc_order_date + datetime.timedelta(days=30)

    # 3. 精确计算剩余时间（天+小时）
    diff_seconds = (deadline - now).total_seconds()
    days_left = int(diff_seconds // (24 * 3600))
    hours_left = int((diff_seconds % (24 * 3600)) // 3600)
    # 生成易读的时间字符串（适配双语前端）
    time_left_str_zh = f"{days_left}天{hours_left}小时" if days_left > 0 else f"{hours_left}小时"
    time_left_str_en = f"{days_left}d {hours_left}h" if days_left > 0 else f"{hours_left}h"

    # 4. 状态判断（过期/紧急/安全）
    if diff_seconds <= 0:
        return {
            "status": "EXPIRED",
            "message_zh": "❌ 已过期！触发2026/02/16新政30天自动拒绝规则，UTC时间已超期。",
            "message_en": "❌ Expired! Triggered 2026/02/16 new policy 30-day automatic rejection rule, UTC time overdue.",
            "days_left": days_left,
            "hours_left": hours_left,
            "time_left_str_zh": time_left_str_zh,
            "time_left_str_en": time_left_str_en,
            "color": "gray"
        }
    elif days_left <= 5:
        return {
            "status": "URGENT",
            "message_zh": f"🚨 紧急！仅剩{time_left_str_zh}处理窗口，请立即准备证据链（重量/物流/序列号）。",
            "message_en": f"🚨 Urgent! Only {time_left_str_en} remaining in processing window, prepare evidence chain immediately (weight/logistics/serial number).",
            "days_left": days_left,
            "hours_left": hours_left,
            "time_left_str_zh": time_left_str_zh,
            "time_left_str_en": time_left_str_en,
            "color": "red"
        }
    else:
        return {
            "status": "SAFE",
            "message_zh": f"✅ 安全！剩余{time_left_str_zh}处理窗口，可合理安排索赔操作。",
            "message_en": f"✅ Safe! {time_left_str_en} remaining in processing window, arrange claim operations reasonably.",
            "days_left": days_left,
            "hours_left": hours_left,
            "time_left_str_zh": time_left_str_zh,
            "time_left_str_en": time_left_str_en,
            "color": "green"
        }

def generate_ai_appeal_draft(reason_code, order_id):
    """
    生成AI申诉信模板（适配亚马逊2026新政，保持英文符合审核要求）
    :param reason_code: 索赔场景（EMPTY_BOX/DAMAGED/SWITCHED）
    :param order_id: 亚马逊订单ID（已校验格式）
    :return: str - 申诉信草稿
    """
    # 校验订单ID格式（二次防护）
    if not check_order_id_format(order_id):
        return "❌ Invalid Order ID format! Please enter like 114-9283-001"

    templates = {
        "EMPTY_BOX": f"""Dear Amazon Support,
This is a formal SAFE-T claim for Order {order_id} (adapt to Amazon 2026 30-day new policy).
The buyer returned an EMPTY PACKAGE, which is a suspicious return behavior. Our outbound shipping weight was 0.8kg, but the returned weight was only 0.05kg (no product included).
We request Amazon to review this claim and arrange the corresponding reimbursement as soon as possible.
Thank you for your processing!""",
        "DAMAGED": f"""Dear Amazon Support,
This is a formal SAFE-T claim for Order {order_id} (adapt to Amazon 2026 30-day new policy).
The product was returned in unsellable condition: it is heavily used with obvious scratches and the original packaging is missing.
According to Amazon's rules, we request a 50% restocking fee for this order. Please review and confirm.
Thank you for your processing!""",
        "SWITCHED": f"""Dear Amazon Support,
This is a formal SAFE-T claim for Order {order_id} (adapt to Amazon 2026 30-day new policy).
The item returned by the buyer is NOT the one we shipped: the serial number on the returned item does not match our outbound delivery records.
This is a clear product switching behavior, we request Amazon to investigate and arrange full reimbursement.
Thank you for your processing!"""
    }
    return templates.get(reason_code, "❌ Unsupported claim reason! Please select EMPTY_BOX/DAMAGED/SWITCHED.")

def gemini_generate_appeal(reason_code, order_id):
    """
    （可选）对接Gemini API生成个性化申诉信（需配置GEMINI_API_KEY）
    :param reason_code: 索赔场景
    :param order_id: 亚马逊订单ID
    :return: str - AI生成的申诉信
    """
    try:
        import google.generativeai as genai
        # 从环境变量获取API Key，避免硬编码
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            return "❌ GEMINI_API_KEY not found! Please configure in .env file."
        
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel("gemini-pro")
        prompt = f"""
        You are an Amazon SAFE-T claim expert, adapted to the 2026 30-day new policy.
        Generate a formal English appeal letter for Order {order_id}, scenario: {reason_code}.
        Requirements: 80-120 words, highlight evidence points (weight/logistics/serial number), comply with Amazon review standards.
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except ImportError:
        return "❌ Please install google-generativeai first: pip install google-generativeai"
    except Exception as e:
        return f"❌ Gemini API error: {str(e)}"

def generate_dashboard_data(test_orders=None):
    """
    生成模拟仪表盘数据（适配前端可视化）
    :param test_orders: 测试订单列表，格式：[{"order_id": "xxx", "order_date": "YYYY-MM-DD"}]
    :return: dict - 仪表盘结构化数据
    """
    if not test_orders:
        # 默认测试数据
        test_orders = [
            {"order_id": "114-9283-001", "order_date": "2026-02-10"},
            {"order_id": "225-8765-002", "order_date": "2026-01-05"},
            {"order_id": "336-7654-003", "order_date": "2026-02-01"}
        ]
    
    dashboard = {
        "total_orders": len(test_orders),
        "expired_orders": 0,
        "urgent_orders": 0,
        "safe_orders": 0,
        "order_details": []
    }

    for order in test_orders:
        # 跳过格式错误的订单ID
        if not check_order_id_format(order["order_id"]):
            continue
        # 计算每个订单的索赔状态
        result = check_safet_deadline(order["order_date"])
        dashboard["order_details"].append({
            "order_id": order["order_id"],
            "order_date": order["order_date"],
            "status": result["status"],
            "time_left_zh": result["time_left_str_zh"],
            "time_left_en": result["time_left_str_en"],
            "message_zh": result["message_zh"],
            "message_en": result["message_en"]
        })
        # 统计各状态订单数
        if result["status"] == "EXPIRED":
            dashboard["expired_orders"] += 1
        elif result["status"] == "URGENT":
            dashboard["urgent_orders"] += 1
        elif result["status"] == "SAFE":
            dashboard["safe_orders"] += 1

    return dashboard

# 本地测试入口（执行脚本时自动运行）
if __name__ == "__main__":
    print("=== SAFE-T Guard 2026 核心逻辑测试 ===")
    
    # 1. 测试订单ID格式校验
    test_order_ids = ["114-9283-001", "123456", "abc-1234-567", "447-8901-004"]
    print("\n--- 订单ID格式校验 ---")
    for oid in test_order_ids:
        print(f"订单ID {oid}: {'通过' if check_order_id_format(oid) else '不通过'}")
    
    # 2. 测试索赔截止时间计算
    test_order_date = "2026-02-10"
    print("\n--- 索赔截止时间计算（UTC校准） ---")
    deadline_result = check_safet_deadline(test_order_date)
    print(f"订单日期：{test_order_date}")
    print(f"中文提示：{deadline_result['message_zh']}")
    print(f"英文提示：{deadline_result['message_en']}")
    
    # 3. 测试申诉信生成
    print("\n--- AI申诉信生成（空包裹场景） ---")
    appeal_draft = generate_ai_appeal_draft("EMPTY_BOX", "114-9283-001")
    print(appeal_draft)
    
    # 4. 测试仪表盘数据生成
    print("\n--- 仪表盘数据生成 ---")
    dashboard = generate_dashboard_data()
    print(f"总订单数：{dashboard['total_orders']}")
    print(f"过期订单数：{dashboard['expired_orders']}")
    print(f"紧急订单数：{dashboard['urgent_orders']}")
    print(f"安全订单数：{dashboard['safe_orders']}")
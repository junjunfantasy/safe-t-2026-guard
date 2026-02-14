# Version: 2026.02.15.v1
import datetime

def check_safet_deadline(order_date_str):
    # 2026年2月16日新政：索赔窗口缩短至30天
    order_date = datetime.datetime.strptime(order_date_str, "%Y-%m-%d")
    deadline = order_date + datetime.timedelta(days=30)
    days_left = (deadline - datetime.datetime.now()).days
    
    if days_left <= 0:
        return "❌ 已过期！无法索赔。原因：触发 2026/02/16 新政 30 天自动拒绝规则。"
    elif days_left <= 2:
        return f"🚨 紧急！仅剩 {days_left} 天，请立即提交证据链（重量对比/照片）。"
    else:
        return f"✅ 安全。剩余 {days_left} 天处理窗口。"

# 模拟测试
print("--- SAFE-T Guard 2026 逻辑审计 ---")
print(check_safet_deadline("2026-02-10"))

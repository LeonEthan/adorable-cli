import random

# 生成10个0到1之间的随机浮点数
random_numbers = [random.uniform(0, 1) for _ in range(10)]

# 打印生成的随机数
print("生成的随机数:")
for i, num in enumerate(random_numbers, 1):
    print(f"{i}: {num:.6f}")  # 格式化为6位小数以更好显示小数

# 额外信息：统计信息
print(f"\n统计信息:")
print(f"最大值: {max(random_numbers):.6f}")
print(f"最小值: {min(random_numbers):.6f}")
print(f"平均值: {sum(random_numbers)/len(random_numbers):.6f}")
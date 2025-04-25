# 定义一个自定义异常
class InvalidAgeError(Exception):
    def __init__(self, message="年龄无效"):
        self.message = message
        super().__init__(self.message)

def check_age(age):
    if age < 0 or age > 150:
        raise InvalidAgeError("年龄必须在 0 到 150 之间")
    return age

try:
    check_age(200)  # 触发自定义异常
except InvalidAgeError as e:
    print(f"捕获到异常: {e}")

import paddle
import paddleocr

print("PaddlePaddle version:", paddle.__version__)
print("PaddleOCR version:", paddleocr.__version__)
print("PaddlePaddle device:", paddle.device.get_device())
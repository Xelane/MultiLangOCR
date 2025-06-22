from paddleocr import PaddleOCR
print(PaddleOCR.get_model_list()['rec']['PP-OCRv4']['en']['use_space_char'])  # should exist

import cv2
import numpy as np
import mss
import keyboard

# Область экрана
monitor = {"top": 400, "left": 700, "width": 300, "height": 300}

# Загружаем эталонную форму (чёрно-белое изображение)
template = cv2.imread("template.png", 0)
_, template_thresh = cv2.threshold(template, 127, 255, cv2.THRESH_BINARY)

# Контуры эталона
contours_template, _ = cv2.findContours(template_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
template_contour = max(contours_template, key=cv2.contourArea)

with mss.mss() as sct:
    print("Зажми SHIFT для активации...")

    while True:
        if keyboard.is_pressed("shift"):
            img = np.array(sct.grab(monitor))
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

            # Бинаризация
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

            # Поиск контуров
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                if cv2.contourArea(cnt) < 500:
                    continue

                # Сравнение формы
                similarity = cv2.matchShapes(template_contour, cnt, 1, 0.0)

                if similarity < 0.2:  # чем меньше — тем больше похоже
                    print("Форма обнаружена!")
                    # действие:
                    # keyboard.press_and_release("space")

        if keyboard.is_pressed("esc"):
            break
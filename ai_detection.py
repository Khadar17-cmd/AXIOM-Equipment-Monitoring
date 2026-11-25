"""
AI detection module.

This project is hardware-free. The web demo accepts an equipment image.
For a real trained model, place your YOLO .pt model in the project and
load it with ultralytics.YOLO.

Example:
    from ultralytics import YOLO
    model = YOLO("models/equipment_model.pt")
"""
def demo_detection(filename):
    name = filename.lower()
    known = {
        "cnc": ("CNC Machine", 94.0),
        "lathe": ("Lathe Machine", 92.0),
        "weld": ("Welding Machine", 90.0),
        "drill": ("Drilling Machine", 91.0),
        "grind": ("Grinding Machine", 89.0),
        "mill": ("Milling Machine", 93.0),
    }
    for key, result in known.items():
        if key in name:
            return result
    return ("Equipment detected - model training required", 75.0)

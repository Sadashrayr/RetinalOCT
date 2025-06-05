from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tf_keras_vis.gradcam import Gradcam
from tf_keras_vis.gradcam_plus_plus import GradcamPlusPlus
from tensorflow.keras.applications.resnet50 import preprocess_input
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
import os
import cv2

try:
    model = load_model("model/retinal_resnet50_finetuned.h5", compile=False)
    # Ensure the model is built for inference
    if not model.built:
        model.build((None, 300, 300, 3))
        print("Model built successfully.")  # Debug
except Exception as e:
    print(f"Error loading model: {e}")
    raise

dataset_folder = r"C:\Users\KIIT\Downloads\Retinal OCT\RetinalOCT_Dataset"


def get_classes(dataset_name):
    dataset_path = os.path.join(dataset_folder, dataset_name)
    return sorted(
        [
            d
            for d in os.listdir(dataset_path)
            if os.path.isdir(os.path.join(dataset_path, d))
        ]
    )


dataset_classes = get_classes("test")


def preprocess_image(image_path):
    img = cv2.imread(image_path)
    if img is not None:
        img = cv2.resize(img, (300, 300))
        img = preprocess_input(img)
        img = np.expand_dims(img, axis=0)
    return img


import os
import numpy as np
import cv2
from tensorflow.keras.models import load_model
from tensorflow.keras.applications.resnet50 import preprocess_input

MODEL_FOLDER = "model"
DATASET_FOLDER = "datasets"

# Load model only once
model = load_model(os.path.join(MODEL_FOLDER, "retinal_resnet50_finetuned.h5"))


# Get class labels dynamically from dataset folder
def get_classes(dataset_name="test"):
    dataset_path = os.path.join(dataset_folder, dataset_name)
    return sorted(
        [
            d
            for d in os.listdir(dataset_path)
            if os.path.isdir(os.path.join(dataset_path, d))
        ]
    )


class_labels = get_classes()


def preprocess_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Image could not be read.")
    img = cv2.resize(img, (300, 300))  # ResNet50 expected input
    img = preprocess_input(img)
    img = np.expand_dims(img, axis=0)
    return img


def predict_image(image_path):
    image = preprocess_image(image_path)
    prediction = model.predict(image)[0]
    predicted_class = np.argmax(prediction)
    confidence = float(np.max(prediction))
    category = class_labels[predicted_class]
    return category, confidence


def generate_heatmap(file_path, scan_id):
    img = load_img(file_path, target_size=(300, 300))
    img_array = img_to_array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    try:
        # Define a model modifier to handle ResNet50 preprocessing
        def model_modifier(m):
            m.layers[-1].activation = (
                tf.keras.activations.linear
            )  # Remove softmax for Grad-CAM
            return m

        # Try GradcamPlusPlus first (more robust for ResNet50)
        try:
            gradcam = GradcamPlusPlus(model, model_modifier=model_modifier, clone=False)
            heatmap = gradcam(
                lambda x: model(x, training=False),
                img_array,
                penultimate_layer="conv5_block3_out",
            )
        except Exception as e:
            print(f"GradcamPlusPlus failed: {e}, falling back to Gradcam")
            gradcam = Gradcam(model, model_modifier=model_modifier, clone=False)
            heatmap = gradcam(
                lambda x: model(x, training=False),
                img_array,
                penultimate_layer="conv5_block3_out",
            )

        # Normalize and save the heatmap
        heatmap = np.uint8(255 * heatmap[0])  # Convert to 0-255 range
        heatmap_path = f"static/uploads/heatmap_{scan_id}.png"
        plt.imsave(heatmap_path, heatmap, cmap="jet")
        print(f"Generated heatmap at: {heatmap_path}")  # Debug
        return heatmap_path
    except Exception as e:
        print(f"Heatmap generation error: {e}")
        raise

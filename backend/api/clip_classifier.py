from transformers import CLIPProcessor, CLIPModel
import torch
from PIL import Image
import requests
from io import BytesIO

# Load the model and processor from Hugging Face
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")

# Define device
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

# Example function to classify design
def classify_design(design):
    """
    Classifies a design into a category using the CLIP model.
    
    Args:
        design (Design): A Design instance containing an image URL.

    Returns:
        str: The category of the design.
    """
    try:
        # Load the image from the URL
        response = requests.get(design.image_url)
        image = Image.open(BytesIO(response.content))

        # Preprocess the image and text for CLIP
        inputs = processor(text=["family", "anime", "tv shows", 'animated character',"pop music culture","pets", "abstract", "nature", "sports"], 
                           images=image, return_tensors="pt", padding=True)

        # Get model outputs
        outputs = model(**inputs)

        # Calculate cosine similarities
        logits_per_image = outputs.logits_per_image  # This is the image-text similarity
        probs = logits_per_image.softmax(dim=1)  # We can get the probability for each class
        
        # Find the category with the highest probability
        category_index = torch.argmax(probs).item()
        categories = ["family", "anime", "tv shows", "pop music culture",'animated character','pets',"nature", "sports"]
        return categories[category_index]
    except Exception as e:
        print(f"Error in classifying design: {e}")
        return "unknown"

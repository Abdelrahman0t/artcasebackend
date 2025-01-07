import requests
import base64
from django.conf import settings

class PrintfulAPI:
    BASE_URL = 'https://api.printful.com/'
    
    def __init__(self):
        self.api_token = settings.PRINTFUL_API_KEY  # Make sure to set this in your settings
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }

    def create_order(self, recipient, items):
        """
        Creates an order in Printful with the specified recipient and items.
        Args:
            recipient (dict): Information about the order recipient (name, address, etc.).
            items (list): A list of item data including the design to print.

        Returns:
            dict: The Printful response as a dictionary.
        """
        url = f'{self.BASE_URL}orders'
        order_data = {
            'recipient': recipient,
            'items': items
        }

        response = requests.post(url, headers=self.headers, json=order_data)
        return response.json()

    def upload_image(self, image_path):
        """
        Uploads a design image to Printful to use in products.
        Args:
            image_path (str): Path to the image to upload.

        Returns:
            dict: The Printful response, including the URL of the uploaded image.
        """
        url = f'{self.BASE_URL}mockup-generator/create-task'

        # Read the image as base64 (necessary for Printful's upload process)
        with open(image_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')

        data = {
            "variant_ids": [1],  # Example variant id (adjust based on product type)
            "image_url": encoded_image,
        }

        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

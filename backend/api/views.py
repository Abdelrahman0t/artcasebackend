from rest_framework import generics,viewsets
from rest_framework.response import Response
from rest_framework import status,permissions
from .models import *
from .serializers import *
import os
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.conf import settings
import requests
from rest_framework.views import APIView
from rest_framework.decorators import api_view ,permission_classes
import logging
from decouple import config
import cloudinary.uploader
from rest_framework.permissions import IsAuthenticated
# Set up logging
logger = logging.getLogger(__name__)
from django.views.decorators.csrf import csrf_exempt
import json
import io
import base64
from django.db.models import Count
from django.db.models import Q
from rest_framework.permissions import AllowAny
SPACE_URL = "https://huggingface.co/spaces/abdelrahmanASDLF/artcasee/api/predict/"






API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-3.5-large"
headers = {
    "Authorization": "Bearer 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"  # Use your Hugging Face token here
}

@csrf_exempt
def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.content

# Generate the image from the API
@csrf_exempt
def generate_image(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt')

            if not prompt:
                return JsonResponse({'error': 'Prompt is required'}, status=400)

            # Prepare the input data for the model
            payload = {
                "inputs": prompt,
                
                  
            }

            # Query the Hugging Face API (or whichever API you are using)
            image_bytes = query(payload)

            # Open the returned image data with PIL
            image = Image.open(io.BytesIO(image_bytes))

            # Convert the image to a buffer (BytesIO)
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            buffered.seek(0)

            # Upload to Cloudinary
            upload_response = cloudinary.uploader.upload(buffered, resource_type="image")

            # Return the Cloudinary URL
            image_url = upload_response['secure_url']  # Use the secure URL for HTTPS

            return JsonResponse({'message': 'Image generated successfully', 'image_url': image_url})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)






from api.clip_classifier import classify_design  # Import the classification function


class DesignListView(generics.ListCreateAPIView):
    queryset = Design.objects.all()
    serializer_class = DesignSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        stock = self.request.data.get('stock', True)  # Default to True if no stock is provided
        price = self.request.data.get('price')  # Get the price from the request

        if price is None:
            raise serializers.ValidationError("Price is required.")

        try:
            price = Decimal(price)
            if price < 0:
                raise serializers.ValidationError("Price cannot be negative.")
        except Exception:
            raise serializers.ValidationError("Invalid price format.")

        # Save the design with the user, stock, and price
        design = serializer.save(user=self.request.user, stock=stock, price=price)

        try:
            classified_type = classify_design(design)  # Assuming classify_design is your classifier
            design.theclass = classified_type  # Assign the classified type to the design
            design.save()
        except Exception as e:
            print(f"Error in classification: {e}")  





@api_view(['DELETE'])
def delete_design(request, design_id):
    """
    Deletes a design if the user is the owner.
    """
    design = get_object_or_404(Design, id=design_id)

    # Check ownership
    if design.user != request.user:
        return Response(
            {"detail": "You do not have permission to delete this design."},
            status=status.HTTP_403_FORBIDDEN
        )

    design.delete()
    return Response(
        {"detail": "Design deleted successfully."},
        status=status.HTTP_200_OK
    )

@api_view(['DELETE'])
def delete_post(request, post_id):
    """
    Deletes a post if the user is the owner.
    """
    post = get_object_or_404(Post, id=post_id)

    # Check ownership
    if post.user != request.user:
        return Response(
            {"detail": "You do not have permission to delete this post."},
            status=status.HTTP_403_FORBIDDEN
        )

    post.delete()
    return Response(
        {"detail": "Post deleted successfully."},
        status=status.HTTP_200_OK
    )

@api_view(['GET'])
def get_design_by_id(request, designid):   
    try:
        # Fetch the design based on the designid
        design = Design.objects.get(id=designid)

        # Serialize the design data
        serializer = DesignSerializer(design)    

        # Check if the user is eligible for a discount
        user = request.user
        serialized_data = serializer.data  # Get serialized data
        if user.is_authenticated and user.is_discount_eligible():
            discounted_price = Decimal(serialized_data['price']) * Decimal(0.75)  # Apply a 25% discount
            serialized_data['price'] = round(discounted_price, 2)  # Update the price in the serialized data

        return Response(serialized_data)  # Return serialized design data in JSON format
    except Design.DoesNotExist:
        return Response({'error': 'Design not found'}, status=status.HTTP_404_NOT_FOUND)       
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)     



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_design_archive(request):
    """
    Retrieve all designs created by the authenticated user, including discounts if eligible.
    """
    user = request.user

    # Fetch all designs created by the authenticated user
    designs = Design.objects.filter(user=user)

    # Pass the request to the serializer context so that we can apply discount logic
    serializer = DesignSerializer(designs, many=True, context={'request': request})
    
    return Response({"user": user.username, "designs": serializer.data})




from PIL import Image
import requests
from io import BytesIO
from cloudinary.uploader import upload



@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def posts(request):
    """
    Handles creating and fetching posts.
    """
    if request.method == 'GET':
        # Fetch all posts
        all_posts = Post.objects.all().order_by('-created_at')
        serializer = PostSerializer(all_posts, many=True)
        return Response(serializer.data)

    if request.method == 'POST':
        # Create a new post
        design_id = request.data.get('design')
        caption = request.data.get('caption')
        description = request.data.get('description')

        try:
            design = Design.objects.get(id=design_id, user=request.user)
        except Design.DoesNotExist:
            return Response({"error": "Design not found or not owned by the user."}, status=status.HTTP_404_NOT_FOUND)

        post = Post.objects.create(user=request.user, design=design, caption=caption, description=description)
        serializer = PostSerializer(post)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def public_posts(request):
    posts = Post.objects.all().select_related('design', 'user')  # Fetch posts with related fields
    serializer = PostSerializer(posts, many=True, context={'request': request})  # Pass request in context

    return Response(serializer.data, status=status.HTTP_200_OK)
###########################################################################################################################################################
@api_view(['GET']) 
def get_user_posts(request, user_id):
    # Fetch the user using the user_id
    user = get_object_or_404(CustomUser, pk=user_id)

    # Fetch posts for the user using the related_name 'posts' (created by the foreign key)
    posts = Post.objects.filter(user=user)  # This fetches all posts related to the user
    
    # Serialize the posts
    serializer = PostSerializer(posts, many=True)
    
    return Response(serializer.data)




from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Post, Like, Favorite, Comment
from .serializers import CommentSerializer

# Toggle like (add or remove)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_like(request, post_id):
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return Response({"error": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

    # Check if the user has already liked the post
    existing_like = Like.objects.filter(user=request.user, post=post).first()

    if existing_like:
        # If the like already exists, remove it
        existing_like.delete()

        # Remove the like notification if it exists
        Notification.objects.filter(
            user=post.user,
            action_user=request.user,
            design=post.design,
            notification_type='like'
        ).delete()

        # Check if the post owner still qualifies for a discount
        post_owner = post.user
        if not post_owner.is_discount_eligible():
            post_owner.is_discount_eligible = False
            post_owner.save()

        return Response({
            "message": "Like removed.",
            "is_liked": False,
            "like_count": post.likes.count()
        }, status=status.HTTP_200_OK)

    # Add the like
    Like.objects.create(user=request.user, post=post)

    # Create a notification when the like is added
    notification_message = f"{request.user.username} liked your design"
    Notification.objects.create(
        user=post.design.user,  # The owner of the design
        action_user=request.user,  # The user who liked the post
        design=post.design,
        notification_type='like',
        message=notification_message
    )

    # Check if the post owner qualifies for a discount
    post_owner = post.user
    if post_owner.is_discount_eligible():
        post_owner.is_discount_eligible = True
        post_owner.save()

    return Response({
        "message": "Like added.",
        "is_liked": True,
        "like_count": post.likes.count()
    }, status=status.HTTP_201_CREATED)


 


# Toggle favorite (add or remove)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_favorite(request, post_id):
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return Response({"error": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

    # Use get_or_create for toggling favorite, and delete if already exists
    favorite, created = Favorite.objects.get_or_create(user=request.user, post=post)

    if not created:  # If the favorite already exists, remove it
        favorite.delete()

        # Remove the favorite notification if it exists
        Notification.objects.filter(user=post.user, action_user=request.user, design=post.design, notification_type='favorite').delete()

        return Response({"message": "Favorite removed."}, status=status.HTTP_204_NO_CONTENT)

    # Create a notification when the favorite is added
    notification_message = f"{request.user.username} favorited your design"
    Notification.objects.create(
        user=post.design.user,  # The owner of the design
        action_user=request.user,  # The user who added to favorites
        design=post.design,
        notification_type='favorite',
        message=notification_message
    )

    return Response({"message": "Favorite added."}, status=status.HTTP_201_CREATED)


# Add a new comment to a post
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_comment(request, post_id):
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return Response({"error": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

    content = request.data.get('content')
    if not content:
        return Response({"error": "Content is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Create the comment
    comment = Comment.objects.create(user=request.user, post=post, content=content)

    # Create a notification for the post owner when a comment is added
    notification_message = f"{request.user.username} commented on your design: {content}"
    Notification.objects.create(
        user=post.design.user,  # The owner of the design
        action_user=request.user,  # The user who commented
        design=post.design,
        notification_type='comment',
        message=notification_message
    )

    return Response({"message": "Comment added.", "comment": CommentSerializer(comment).data}, status=status.HTTP_201_CREATED)


# Delete a comment
@api_view(['DELETE'])
def delete_comment(request, comment_id):
    try:
        comment = Comment.objects.get(id=comment_id)
    except Comment.DoesNotExist:
        return Response({"error": "Comment not found."}, status=status.HTTP_404_NOT_FOUND)

    if comment.user != request.user:
        return Response({"error": "You can only delete your own comments."}, status=status.HTTP_403_FORBIDDEN)

    # Delete the notification related to this comment if it exists
    Notification.objects.filter(user=comment.post.design.user, action_user=request.user, design=comment.post.design, notification_type='comment').delete()

    comment.delete()
    return Response({"message": "Comment deleted."}, status=status.HTTP_204_NO_CONTENT)




@api_view(['GET'])
def get_comments(request, post_id):
    try:
        # Fetch all comments for the given post
        comments = Comment.objects.filter(post_id=post_id)
        
        # Serialize the comments
        serializer = CommentSerializer(comments, many=True)
        
        # Return the list of comments as a response
        return Response({'comments': serializer.data}, status=status.HTTP_200_OK)
    except Comment.DoesNotExist:
        return Response({'error': 'Comments not found for this post'}, status=status.HTTP_404_NOT_FOUND)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_favorites(request):
    """
    Get all designs favorited by the authenticated user.
    """
    favorites = Favorite.objects.filter(user=request.user)
    designs = [favorite.post.design for favorite in favorites]

    # Pass the request to the serializer's context
    serializer = DesignSerializer(designs, many=True, context={'request': request})

    return Response({"favorites": serializer.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_liked(request):
    """
    Get all designs liked by the authenticated user.
    """
    liked_designs = Like.objects.filter(user=request.user)
    designs = [like.post.design for like in liked_designs]

    # Pass the request to the serializer's context
    serializer = DesignSerializer(designs, many=True, context={'request': request})

    return Response({"liked": serializer.data}, status=status.HTTP_200_OK)



 
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    user = request.user

    # Get all notifications for the user, ordered by the creation date (most recent first)
    notifications = Notification.objects.filter(user=user).order_by('-created_at')

    # Serialize the notifications
    serializer = NotificationSerializer(notifications, many=True)

    return Response({'notifications': serializer.data}, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_read(request, notification_id):
    try:
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        notifications.update(is_read=True)
        return Response({"message": "All notifications marked as read."}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
    except Notification.DoesNotExist:
        return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)

    notification.delete()

    return Response({"message": "Notification deleted."}, status=status.HTTP_204_NO_CONTENT)



@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Ensure the user is logged in
def add_to_cart(request):
    user = request.user
    design_id = request.data.get('design_id')

    # Validate if design_id is provided
    if not design_id:
        return Response({"error": "Design ID is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Check if the design exists
    design = get_object_or_404(Design, id=design_id)

    # Check if the item is already in the cart
    if Chart.objects.filter(user=user, design=design).exists():
        return Response({"error": "This item is already in your cart."}, status=status.HTTP_400_BAD_REQUEST)

    # Calculate the discounted price if the user is eligible
    price = design.price
    if user.is_discount_eligible():
        price *= Decimal('0.75')  # Apply a 25% discount

    # Add the item to the cart
    cart_item = Chart.objects.create(user=user, design=design, price=price)  # Assuming `Chart` has a `price` field
    return Response({"message": "Item added to cart successfully!"}, status=status.HTTP_201_CREATED)



@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Ensure the user is logged in
def view_cart(request):
    user = request.user
    cart_items = Chart.objects.filter(user=user)
    serializer = ChartSerializer(cart_items, many=True)
    return Response(serializer.data, status=200)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])  # Ensure the user is logged in
def delete_from_cart(request, cart_id):
    user = request.user
    cart_item = get_object_or_404(Chart, id=cart_id, user=user)
    cart_item.delete()
    return Response({"message": "Item removed from cart successfully!"}, status=status.HTTP_200_OK)












@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_posts(request):
    """
    Fetch all posts by the authenticated user.
    """
    user_posts = Post.objects.filter(user=request.user).order_by('-created_at')
    serializer = PostSerializer(user_posts, many=True)
    return Response(serializer.data)

#cloud secret key = 6qL3HdWcb3HJ72iqIGnDMRkVNd8
#cloud api key = 428318487815239

# =======================================================================================
#recipe :  a76c916b-1ea8-4a18-b378-07ec7f18e164
#bill : Kd+wOqFRk0btkCgQc7HYxRU2OuxA6xbq0W3JekY6FNs=

def resize_image(image_url):
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))

    # Resize the image to 1176 x 2060px
    img = img.resize((1176, 2060))

    # Save the resized image to a buffer
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)  # Ensure the pointer is at the start of the buffer

    return buffer

# Function to upload image to Cloudinary and return the URL
def upload_to_cloudinary(image_buffer):
    response = upload(image_buffer)
    return response['url']  # Return the URL of the uploaded image








@api_view(['POST', 'GET'])
def test(request):
    api_key = "iffjgbnj8L+n8rjqBnhuAhJ6b/F1x7hFNO0H8B43h9w="
    recipe_id = "b906a8c2-8670-4f6e-acf0-b2a9832e82eb"


    design_id = request.data.get("design")
    phone_number = request.data.get("phone_number")
    address = request.data.get("address")
    city = request.data.get("city")
    country = request.data.get("country")
    first_name = request.data.get("firstname")
    last_name = request.data.get("lastname")  
    email = request.data.get("email")   
    sku = request.data.get("sku")
     
    try:
        design = Design.objects.get(id=design_id)
    except Design.DoesNotExist:
        return Response({"error": "Design not found"}, status=status.HTTP_404_NOT_FOUND)
    
    order_data = {
        "Items": [
            {
                "SKU": sku,
                "Quantity": 1,
                "Images": [
                    {
                        "Url": design.image_url,
                        "UseUrlAsImageID": False,  # Use URL as image source
                        "Position": {
                            "X": 0.5,  # Center image on X-axis
                            "Y": 0.5,  # Center image on Y-axis
                            "ScaleX": 1.0,  # Scale to fit
                            "ScaleY": 1.0,  # Scale to fit
                            "Rotation": 0,  # No rotation needed
                        },
                        "PrintArea": {
                            "Width": 1176 ,  # Use the actual print area width
                            "Height": 2060,  # Use the actual print area height
                        }
                    }
                ]
            }
        ],
        "ShipToAddress": {
            "FirstName": first_name,
            "LastName": last_name,
            "Line1": "123 Main St",
            "City": city,
            "State": "NY",
            "PostalCode": "10001",
            "CountryCode": country,
            "Phone": phone_number,  # Ensure phone_number is included here
            "Email": email, 
        },
        "BillingAddress": {
            "FirstName": first_name,
            "LastName": last_name,
            "Line1": "123 Main St",
            "City": city,
            "State": "NY",
            "PostalCode": "10001",
            "CountryCode": country,
            "Phone": phone_number,  # Include phone_number in billing if required
            "Email": email,  
        },
        "Payment": {
            "CurrencyCode": "USD",
            "PartnerBillingKey": "iffjgbnj8L+n8rjqBnhuAhJ6b/F1x7hFNO0H8B43h9w=" #============================================<<<<<<<<<<<<<<<<<<<<<<<<
        },
        "IsPackingSlipEnabled": True,  # Explicitly enable packing slips
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    url = f"https://api.print.io/api/orders?recipeId={recipe_id}"
    res = requests.post(url=url, headers=headers, json=order_data) 
    
    if res.status_code == 200:
        return Response(res.json(), status=status.HTTP_201_CREATED)
    else:
        return Response({"error": res.json()}, status=res.status_code)






@api_view(['GET'])
def get_phone_cases(request):

    GOOTEN_API_KEY = "Kd+wOqFRk0btkCgQc7HYxRU2OuxA6xbq0W3JekY6FNs="
    recipe_id = "a76c916b-1ea8-4a18-b378-07ec7f18e164"
    GOOTEN_PRODUCTS_URL = "https://api.print.io/api/v/6/source/api/products"

    """
    Fetch all phone case types from Gooten API.
    """
    try:
        # Include the API key as a query parameter
        params = {
            "apiKey": GOOTEN_API_KEY,
        }
        response = requests.get(GOOTEN_PRODUCTS_URL, params=params)
        response_data = response.json()

        # Filter phone case products
        phone_cases = [
            product for product in response_data.get("Products", [])
            if "phone case" in product.get("Name", "").lower()
        ]

        # Return the filtered list
        return Response({"phone_cases": phone_cases}, status=response.status_code)
    
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    

    

@api_view(["GET"])
def get_templates(request):
    api_key = "Kd+wOqFRk0btkCgQc7HYxRU2OuxA6xbq0W3JekY6FNs="
    recipe_id = "a76c916b-1ea8-4a18-b378-07ec7f18e164"
    
    # Construct the request URL
    url = f"https://api.print.io/api/v/5/source/api/producttemplates/?recipeid={recipe_id}&sku=PremiumPhoneCase-iPhone-15-pro-SnapCaseGloss"
    
    # Set the headers with API key and content type
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        # Send GET request to Gooten API
        res = requests.get(url, headers=headers)

        # Check for successful response
        if res.status_code == 200:
            # Parse the JSON response
            data = res.json()
            return Response(data, status=status.HTTP_200_OK)
        else:
            # Handle non-200 responses
            return Response({"error": res.content.decode()}, status=res.status_code)
    
    except Exception as e:
        # Handle any request exceptions
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    








@api_view(['POST'])
def creatte_order(request):
    """
    API view to create an order using the OrderSerializer.
    Validates the quantity to ensure it does not exceed 9.
    """
    # Get the order data from the request
    order_data = request.data
    
    # Check if the quantity is greater than 9
    quantity = order_data.get('quantity', 1)  # Default to 1 if quantity is not provided
    if quantity > 9:
        return Response(
            {"error": "Quantity cannot exceed 9."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Proceed with serialization and saving the order if quantity is valid
    serializer = OrderSerializer(data=order_data)
    
    if serializer.is_valid():
        # Save the order with the authenticated user, if applicable
        user = request.user if request.user.is_authenticated else None
        serializer.save(user=user)
        return Response(
            {"message": "Order created successfully", "order": serializer.data},
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    

 
@csrf_exempt  # Disable CSRF for testing purposes
@api_view(['DELETE'])  # Allow only DELETE method for this view
def cancel_order(request, order_id): 
    try:
        # Get the order object by its ID
        order = Order.objects.get(id=order_id)
        
        # Ensure the order status is 'pending' before allowing deletion
        if order.status == 'pending':
            order.delete()  # Delete the order
            return Response({"message": "Order has been deleted successfully."}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Order cannot be deleted. It is either completed or canceled."}, status=status.HTTP_400_BAD_REQUEST)

    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

     
@api_view(['GET'])
def get_user_orders(request):
    """
    API view to get all orders for the authenticated user.
    """
    if not request.user.is_authenticated:
        return Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_403_FORBIDDEN
        )

    # Filter orders by the authenticated user
    orders = Order.objects.filter(user=request.user)

    # Serialize the orders and return them
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
def cancel_order(request, order_id):          
    """
    API view to cancel an order by its ID.
    """
    try:
        # Fetch the order
        order = Order.objects.get(id=order_id)

        # Check if the order can be canceled
        if order.status == 'canceled':
            return Response(
                {"message": "Order is already canceled."},
                status=status.HTTP_400_BAD_REQUEST
            )     
        elif order.status == 'completed':
            return Response(
                {"message": "Completed orders cannot be canceled."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update the status to 'canceled'
        order.status = 'canceled'
        order.save()

        return Response(
            {"message": f"Order {order.id} has been canceled successfully."},
            status=status.HTTP_200_OK
        )

    except Order.DoesNotExist:
        return Response(
            {"error": "Order not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    # Replace with your actual API token
    api_token = 'J5O5PrGXT4q0Qvs75Z16JIOvs4BmB5Gk5ZqusZe6'
    
    # Example order data
    order_data = {
        "external_id": "4235234213",
        "shipping": "STANDARD",
        "recipient": {
            "name": "John Smith",
            "company": "John Smith Inc",
            "address1": "19749 Dearborn St",
            "address2": "string",
            "city": "Chatsworth",
            "state_code": "CA",
            "state_name": "California",
            "country_code": "US",
            "country_name": "United States",
            "zip": "91311",
            "phone": "2312322334",
            "email": "firstname.secondname@domain.com",
            "tax_number": "123.456.789-10"
        },
        "items": [
            {
                "id": 1,
                "external_id": "item-1",
                "variant_id": 1,
                "sync_variant_id": 1,
                "external_variant_id": "variant-1",
                "warehouse_product_variant_id": 1,
                "product_template_id": 1,
                "external_product_id": "template-123",
                "quantity": 1,
                "price": "13.00",
                "retail_price": "13.00",
                "name": "Enhanced Matte Paper Poster 18×24",
                "product": {
                    "variant_id": 3001,
                    "product_id": 301,
                    "image": "https://files.cdn.printful.com/products/71/5309_1581412541.jpg",
                    "name": "Bella + Canvas 3001 Unisex Short Sleeve Jersey T-Shirt with Tear Away Label (White / 4XL)"
                },
                "files": [
                    {
                        "type": "default",
                        "url": "https://www.example.com/files/tshirts/example.png",
                        "options": [
                            {
                                "id": "template_type",
                                "value": "native"
                            }
                        ],
                        "filename": "shirt1.png",
                        "visible": True,
                        "position": {
                            "area_width": 1800,
                            "area_height": 2400,
                            "width": 1800,
                            "height": 1800,
                            "top": 300,
                            "left": 0,
                            "limit_to_print_area": True
                        }
                    }
                ],
                "options": [
                    {
                        "id": "OptionKey",
                        "value": "OptionValue"
                    }
                ],
                "sku": None,
                "discontinued": True,
                "out_of_stock": True
            }
        ],
        "retail_costs": {
            "currency": "USD",
            "subtotal": "10.00",
            "discount": "0.00",
            "shipping": "5.00",
            "tax": "0.00"
        },
        "gift": {
            "subject": "To John",
            "message": "Have a nice day"
        },
        "packing_slip": {
            "email": "your-name@your-domain.com",
            "phone": "+371 28888888",
            "message": "Message on packing slip",
            "logo_url": "http://www.your-domain.com/packing-logo.png",
            "store_name": "Your store name",
            "custom_order_id": "kkk2344lm"
        }
    }

    # Make the request to the Printful API
    response = requests.post(
        'https://api.printful.com/orders/',
        headers={
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        },
        json=order_data
    )

    # Handle the response
    if response.status_code == 200:
        return Response(response.json(), status=200)
    else:
        return Response({
            'error': 'Failed to communicate with Printful',
            'details': response.json()  # More details from the Printful response
        }, status=response.status_code)







class TestOrderView(APIView):
    def post(self, request, *args, **kwargs):
        # Example static order payload for Printful API
        test_order_payload = {
            "external_id": "test-order-123",
            "shipping": "STANDARD",
            "recipient": {
                "name": "John Doe",
                "company": "Test Company",
                "address1": "123 Test St",
                "address2": "",
                "city": "Test City",
                "state_code": "CA",
                "country_code": "US",
                "zip": "90001",
                "phone": "1234567890",
                "email": "john.doe@example.com",
            },
            "items": [
                {
                    "variant_id": "670e2c2e90d783",  # Example product variant (a t-shirt in this case)
                    "quantity": 1,
                    "name": "Test Product",
                    "files": [
                        {
                            "type": "default",
                            "url": "https://www.example.com/files/design.png"
                        }
                    ]
                }
            ]
        }
        
        try:
            # Send the test order to Printful
            response = requests.post(
                "https://api.printful.com/orders",
                json=test_order_payload,
                headers={
                    "Authorization": f"Bearer {settings.PRINTFUL_API_TOKEN}",
                    "Content-Type": "application/json",
                }
            )
            
            # Check for successful response
            response.raise_for_status()
            
            # Return the successful response from Printful
            return Response(response.json(), status=status.HTTP_200_OK)
        
        except requests.exceptions.HTTPError as http_err:
            return Response(
                {"error": "Failed to communicate with Printful", "details": str(http_err)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except Exception as err:
            return Response(
                {"error": "An unexpected error occurred", "details": str(err)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )















@api_view(['POST'])
def create_product_view(request):
    design_id = request.data.get('design_id')

    if not design_id:
        return Response({"error": "Design ID is required."}, status=status.HTTP_400_BAD_REQUEST)

    design = get_object_or_404(Design, id=design_id)
    image_url = design.image.url  # Ensure this URL is valid and accessible

    api_token = 'J5O5PrGXT4q0Qvs75Z16JIOvs4BmB5Gk5ZqusZe6'  # Replace with your actual API token
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "name": "Your Custom Product Name",
        "type": "apparel",
        "variants": [
            {
                "variant_id": "670e2c2e90d783",  # Ensure this ID is valid
                "files": [
                    {
                        "type": "default",
                        "url": image_url,  # Your image URL from the database
                        "visible": True,
                        "position": {
                            "area_width": 1800,
                            "area_height": 2400,
                            "width": 1800,
                            "height": 1800,
                            "top": 300,
                            "left": 0,
                            "limit_to_print_area": True
                        }
                    }
                ],
                "options": []  # Add actual options if needed
            }
        ]
    }

    response = requests.post("https://api.printful.com/products", json=payload, headers=headers)

    if response.status_code in (200, 201):
        return Response(response.json(), status=status.HTTP_201_CREATED)
    else:
        return Response(response.json(), status=response.status_code)


from rest_framework_simplejwt.tokens import RefreshToken


@api_view(['POST'])
def registerview(request):
    if request.method == "POST":
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
             
            # Check if a profile picture was uploaded
            profile_pic = request.FILES.get('profile_pic')
            if profile_pic:
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(profile_pic, folder="profile_pics")
                # Update the user profile with the Cloudinary URL
                user.profile_pic = upload_result['url']
                user.save()

            # Create JWT tokens for the new user
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            # Return response with tokens and user data
            return Response({
                'user': serializer.data,
                'access_token': access_token,
                'refresh_token': str(refresh)
            }, status=status.HTTP_201_CREATED)
        else:
            # Return validation errors
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        







@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def profile_view(request):
    user = request.user

    # Handle profile picture with a default path if not present


    profile_data = {
        "id" : user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "profile_pic": user.profile_pic
    }
    
    return Response(profile_data)











@api_view(['GET'])
def user_list(request):
    try:
        users = CustomUser.objects.all()  # Get all users
        serializer = UserSerializer(users, many=True)  # Serialize the list of users
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    




@api_view(['GET'])
def user_detail(request, id):
    try:
        user = CustomUser.objects.get(id=id)  # Get user by id
        serializer = UserSerializer(user)  # Serialize the user
        return Response(serializer.data)
    except CustomUser.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    





@api_view(['GET'])
def most_liked_designs(request):
    try:
        # Fetch designs with their related post like counts
        designs = Design.objects.annotate(
            like_count=Count('posts__likes')
        ).filter(like_count__gt=0)  # Get designs with at least one like

        # Limit the designs by the most likes (using Python)
        designs = sorted(designs, key=lambda x: x.like_count, reverse=True)[:10]

        if not designs:
            return Response({'message': 'No liked designs available'}, status=status.HTTP_200_OK)

        # Fetch posts related to these designs
        posts = Post.objects.filter(design__in=designs).select_related('design', 'user')
        post_serializer = PostSerializer(posts, many=True, context={'request': request})

        return Response(post_serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def most_added_to_cart_designs(request):
    try:
        # Fetch designs with their related cart counts
        designs = Design.objects.annotate(
            cart_count=Count('chart')
        ).filter(cart_count__gt=0)  # Get designs with at least one cart addition

        if not designs.exists():
            return Response({'message': 'No designs added to cart yet'}, status=status.HTTP_200_OK)

        # Sort the designs by cart count in descending order (using Python)
        designs = sorted(designs, key=lambda x: x.cart_count, reverse=True)[:10]

        # Fetch posts related to these top 10 designs
        posts = Post.objects.filter(design__in=designs).select_related('design', 'user')
        post_serializer = PostSerializer(posts, many=True, context={'request': request})

        return Response(post_serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)      
    


from django.contrib.auth import get_user_model

from django.db.models import Count, Sum
      

from django.db.models import Count, Sum, Q

@api_view(['GET'])
def search(request):
    query = request.GET.get('query', '')  # Get the search query from the request
    if query:
        try:
            # Get the custom User model
            User = get_user_model()

            # Search in the Post model
            posts = Post.objects.filter(
                Q(caption__icontains=query) |  # Case-insensitive search for caption
                Q(description__icontains=query) |  # Case-insensitive search for description
                Q(design__modell__icontains=query) |  # Search in the design's modell field
                Q(design__sku__icontains=query) |  # Search in the design's SKU
                Q(design__type__icontains=query) |  # Search in the design's type
                Q(design__theclass__icontains=query)  # Search in the design's theclass field
            ).select_related('design', 'user')  # Preload related data

            # Search in the User model
            users = User.objects.filter(
                Q(username__icontains=query) |  # Case-insensitive search for username
                Q(first_name__icontains=query) |  # Case-insensitive search for first name
                Q(last_name__icontains=query) |  # Case-insensitive search for last name
                Q(email__icontains=query)  # Case-insensitive search for email
            ).annotate(
                total_posts=Count('post', distinct=True),  # Count distinct posts for each user
                total_likes=Count('post__likes', distinct=True)  # Count distinct Like objects across user's posts 
            )

            # Serialize the results
            post_serializer = PostSerializer(posts, many=True, context={'request': request})

            # Manually include total_posts and total_likes in user serialization
            user_data = []
            for user in users:
                user_data.append({
                    'id': user.id, 
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'profile_pic': user.profile_pic,
                    'total_posts': user.total_posts,
                    'total_likes': user.total_likes if user.total_likes is not None else 0
                })

            # Combine and return the results
            return Response({
                'posts': post_serializer.data,
                'users': user_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return Response({'message': 'No search query provided.'}, status=status.HTTP_400_BAD_REQUEST)
 
 


    

@api_view(['GET', 'POST'])
def fetch_stickers(request):
    # Replace with your actual Flaticon API key
    api_key = 'FPSXf8d02bb7c934441eae5a6b32275a4f9a' 
    url = 'https://api.freepik.com/v1/icons'
    
    headers = {
        "x-freepik-api-key": api_key,
    }
    
    # Default pagination parameters
    page = 1  # Start at page 1
    limit = 100  # Limit the results per page, e.g., 100 per page
    total_stickers = 0  # Track the total number of stickers fetched
    required_stickers = 200  # Set the minimum number of stickers required
    all_icons = []  # List to store all fetched stickers
    params = {
      # Keyword to filter icons by type
    'page': page,
    'limit': limit,  
"term":"emoji",
"filters[shape]":"lineal-color"   
} 
    try:      
        while total_stickers < required_stickers:
            # Add pagination parameters to the request  
            response = requests.get(url, headers=headers, params=params) 
            response.raise_for_status()  # Raise an error for HTTP 4xx/5xx responses
            data = response.json()  

            icons = data.get('data', [])  
            all_icons.extend(icons)  # Add icons from the current page to the list
            total_stickers += len(icons)  # Increment the total stickers count

            # If there are fewer icons than requested, stop fetching
            if len(icons) < limit:
                break
             
            # Move to the next page
            page += 1

        return JsonResponse({"data": all_icons[:required_stickers]}, safe=False)  # Return only up to 200 stickers

    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': 'Failed to fetch resources', 'details': str(e)}, status=500)
    



@api_view(['GET', 'POST'])
def fetch_emoji(request):
    # Replace with your actual Flaticon API key
    # Your Emoji API key
    access_key = 'e4aece1920eea4d2634a2d31588b7b9a8362f89a'
    
    # Emoji API URL with your access key
    url = f"https://emoji-api.com/categories/travel-places?access_key={access_key}"
    
    try:
        # Making a GET request to the Emoji API
        response = requests.get(url)
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Get the emoji data
        emojis = response.json()
        
        # Return the emoji data as JSON
        return Response({"data": emojis}, status=200)
    
    except requests.exceptions.RequestException as e:
        # Handle any errors that occurred during the request
        return Response({'error': 'Failed to fetch emojis', 'details': str(e)}, status=500)
    

@api_view(['GET'])
def get_user_details(request, user_id):
    try:
        user = CustomUser.objects.get(id=user_id)
        return Response({
            'id' : user.id,
            'username': user.username,  # Or any other fields you want to expose
        })
    except CustomUser.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)



@api_view(['GET'])
def top_users_by_likes(request):
    try:
        # Annotate users with the total likes on their posts
        users = CustomUser.objects.annotate(
            total_likes=Count('post__likes'),
            total_posts=Count('post')       
        ).filter(total_likes__gt=0).order_by('-total_likes')[:4]
        data = [
            {
                'user_id': user.id,     
                'username': user.username,
                'profile_pic': user.profile_pic,    
                 'email' : user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,

                'total_likes': user.total_likes,
                'total_posts': user.total_posts  # Add total posts
            }
            for user in users
        ]
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def top_users_by_posts(request):
    try:
        # Annotate users with the total likes on their posts and total posts
        users = CustomUser.objects.annotate(
            total_likes=Count('post__likes'),
            total_posts=Count('post')
        ).filter(total_posts__gt=0).order_by('-total_posts')[:4]  # Order by total posts
        
        data = [
            {
                'user_id': user.id,
                'username': user.username,
                'profile_pic': user.profile_pic,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'total_likes': user.total_likes,
                'total_posts': user.total_posts  # Add total posts
            }
            for user in users
        ]
        
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  
    




@api_view(['GET'])
def recent_posts(request):
    """
    Retrieves the most recent posts.
    """
    # Retrieve the most recent posts, ordered by creation date (descending)
    posts = Post.objects.all().order_by('-created_at')[:10]  # Adjust number as needed

    # Serialize the posts
    serializer = PostSerializer(posts, many=True, context={'request': request})

    return Response(serializer.data, status=status.HTTP_200_OK)


from rest_framework.exceptions import NotFound
@api_view(['GET'])

def get_post_by_id(request, id):
    """
    Retrieve a specific post by its ID.
    """
    try:
        post = Post.objects.get(id=id)
    except Post.DoesNotExist:  
        raise NotFound(detail="Post not found.")
    
    serializer = PostSerializer(post, context={'request': request})
    return Response(serializer.data)

#live_UCW4Io0BICBZ2jeolZMWZhisEanGXIaJIZYPhvcktIY1aD7Mhf3AVoLLMgGxVytN



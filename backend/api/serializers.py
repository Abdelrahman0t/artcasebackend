# serializers.py
from rest_framework import serializers
from .models import *
from .models import CustomUser
import os
import cloudinary
import cloudinary.uploader

from django.db.models import Count, Sum

class ImageGenerationRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=255)
    scheduler = serializers.CharField(required=False, default="K_EULER")

    

from decimal import Decimal

class DesignSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)
    posts = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)  # Accept price from the frontend

    class Meta:
        model = Design
        fields = ["id", "image_url", "user", "stock", "modell", "type", "sku", "price", "theclass", "posts"]

    def validate_price(self, value):
        """Ensure the price is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def get_posts(self, obj):
        posts = obj.posts.all()
        posts_data = PostSerializer(posts, many=True, context=self.context).data

        # Update stock field in the post data to a string representation
        for post_data in posts_data:
            post_data['stock'] = "In Stock" if obj.stock else "Out of Stock"

        return posts_data

    def get_stock(self, obj):
        # Convert the stock field to a human-readable string for the design itself
        return "In Stock" if obj.stock else "Out of Stock"




 
        
class PostSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    profile_pic = serializers.CharField(source='user.profile_pic', read_only=True)

    design = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(source='likes.count', read_only=True)
    comment_count = serializers.IntegerField(source='comments.count', read_only=True)
    favorite_count = serializers.IntegerField(source='favorites.count', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'design', 'caption', 'description', 'user', 'user_id',
            'created_at', 'like_count', 'comment_count', 'favorite_count',
            'first_name', 'profile_pic'
        ]

    def get_design(self, obj):
        """
        Prepares the design data for serialization and applies discounts for eligible users.
        """
        request = self.context.get('request')  # Get the request from the context
        user = request.user if request else None  # Get the authenticated user

        # Default price
        price = obj.design.price

        # Apply discount for eligible users only if the design is not their own  

        stock_status = "In Stock" if obj.design.stock else "Out of Stock" 

        return {
            'id': obj.design.id,
            'image_url': obj.design.image_url,
            'stock': stock_status,  # String representation of stock
            'modell': obj.design.modell,
            'type': obj.design.type,
            'sku': obj.design.sku,
            'price': str(price),  # Return price as string
            'theclass': obj.design.theclass
        }

    def get_is_liked(self, obj):
        user = self.context.get('request').user
        return obj.likes.filter(id=user.id).exists() if user.is_authenticated else False

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        return obj.favorites.filter(id=user.id).exists() if user.is_authenticated else False




class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'id', 'image_url', 'user', 'sku', 'email', 'first_name', 
            'last_name', 'phone_number', 'address', 'city', 
            'country', 'price', 'quantity','status','modell','type'  
        ]
        read_only_fields = ['id', 'user']   

   
 
   



class NotificationSerializer(serializers.ModelSerializer):
    action_user = serializers.CharField(source='action_user.username', read_only=True)
    design_image_url = serializers.CharField(source='design.image_url', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'message', 'notification_type', 'created_at', 'is_read', 'action_user', 'design_image_url']







class ChartSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)
    design = serializers.SerializerMethodField()

    class Meta:
        model = Chart
        fields = ['id', 'design', 'added_at', 'user', 'price']  # Include the price field

    def get_design(self, obj):
        stock_status = "In Stock" if obj.design.stock else "Out of Stock"
        return {
            'id': obj.design.id,
            "image_url": obj.design.image_url,
            "stock": stock_status,
            "modell": obj.design.modell,
            "type": obj.design.type,
            "sku": obj.design.sku,
            'price' : obj.design.price   
        }



class LikeSerializer(serializers.ModelSerializer):
    # Include the like count (number of likes on the post) in the serializer
    post_like_count = serializers.IntegerField(source='post.likes.count', read_only=True)

    class Meta:
        model = Like
        fields = ['id', 'user', 'post', 'created_at', 'post_like_count']


class CommentSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id')  # Get user ID
    username = serializers.CharField(source='user.username')  # Get username
    profile_pic = serializers.CharField(source='user.profile_pic')  # Get username
    first_name = serializers.CharField(source='user.first_name')  # Get username


    class Meta:
        model = Comment
        fields = ['id', 'content', 'created_at', 'user_id', 'username',"profile_pic",'first_name']


class FavoriteSerializer(serializers.ModelSerializer):
    # Include the favorite count (number of favorites on the post) in the serializer
    post_favorite_count = serializers.IntegerField(source='post.favorites.count', read_only=True)

    class Meta:
        model = Favorite
        fields = ['id', 'user', 'post', 'created_at', 'post_favorite_count']




       







class UserSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CustomUser
        fields = ['id','username', 'password', 'first_name', 'last_name', 'email', 'profile_pic']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        profile_pic_url = validated_data.pop('profile_pic', None)

        # Validate the profile picture URL
        if profile_pic_url:
            validated_data['profile_pic'] = profile_pic_url
        else:
            # Set a default Cloudinary image URL if no profile_pic is provided
            validated_data['profile_pic'] = 'https://res.cloudinary.com/daalfrqob/image/upload/v1730076406/default-avatar-profile-trendy-style-social-media-user-icon-187599373_jtpxbk.webp'

        # Create the user with the validated data
        user = CustomUser.objects.create_user(**validated_data)
        return user 
    


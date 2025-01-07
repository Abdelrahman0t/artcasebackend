# models.py
from django.db import models
from django.contrib.auth.models import User,AbstractUser, Group, Permission
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum

class Post(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Reference to the user
    design = models.ForeignKey('Design', on_delete=models.CASCADE, related_name='posts')  # Reference to the design
    caption = models.CharField(max_length=255)  # Caption for the post
    description = models.TextField()  # Detailed description of the post
    created_at = models.DateTimeField(auto_now_add=True)  # Date of post creation

    def __str__(self):
        return f"Post by {self.user.username} on {self.created_at}"


class Design(models.Model):
    image_url = models.URLField()  # The image URL of the design
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Reference to the user who created it
    stock = models.BooleanField()  # Availability of the design (in stock or not)
    modell = models.CharField(max_length=100)  # Model type
    type = models.CharField(max_length=100)  # Type of design (e.g., clear case, solid case)
    sku = models.CharField(max_length=100)  # SKU for the design
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)  # Price of the design
    theclass = models.CharField(max_length=100, blank=True, null=True)  # Classification (optional)
    created_at = models.DateTimeField(auto_now_add=True)  # When the design was created

    def __str__(self):
        return f"Design by {self.user.username} on {self.created_at}"


class Chart(models.Model):
    design = models.ForeignKey('Design', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Reference to the user who created it
    added_at = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    def __str__(self):
        return f"Design by {self.user.username} on {self.added_at}"

    







    
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('like', 'Like'),
        ('comment', 'Comment'),
        ('favorite', 'Favorite'),
        ('order', 'Order'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")  # The user who will receive the notification
    action_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="actions")  # The user who performed the action
    design = models.ForeignKey('Design', on_delete=models.CASCADE)  # The design related to the notification
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES)  # The type of notification (like, comment, etc.)
    message = models.CharField(max_length=255)  # The message that will be shown to the user
    is_read = models.BooleanField(default=False)  # To check whether the notification has been read
    created_at = models.DateTimeField(auto_now_add=True)  # The time when the notification was created

    def __str__(self):
        return f"{self.user.username} - {self.notification_type} - {self.created_at}"

    class Meta:
        ordering = ['-created_at']  # Notifications are ordered by creation date (most recent first)


class CustomUser(AbstractUser):
    is_discount_eligible = models.BooleanField(default=False)
    profile_pic = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        default='https://res.cloudinary.com/daalfrqob/image/upload/v1730076406/default-avatar-profile-trendy-style-social-media-user-icon-187599373_jtpxbk.webp'
    )

    def is_discount_eligible(self):
        # Check if the user's posts have received at least two likes
        return Like.objects.filter(post__user=self).count() >= 2




class Like(models.Model): 
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Prevent duplicate likes

    def __str__(self):
        return f"{self.user.username} liked {self.post.id}"


class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on Post {self.post.id}"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Prevent duplicate favorites

    def __str__(self):
        return f"{self.user.username} favorited {self.post.id}"






 
class Order(models.Model):
    image_url = models.URLField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sku = models.CharField(max_length=200)
 
    modell = models.CharField(max_length=100)  # Model type
    type = models.CharField(max_length=100)
    # Additional fields to store user information
    email = models.EmailField(blank=True, null=True)  # Allow blank initially
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    phone_number = models.IntegerField()
    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    
    # New fields for price and quantity
    price = models.DecimalField(max_digits=10, decimal_places=2)  # E.g., 99999999.99
    quantity = models.PositiveIntegerField(default=1) 


    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )

    def __str__(self):
        return f"Order by {self.first_name} {self.last_name} ({self.email}) - {self.quantity} x {self.price}"

    

class UserDiscount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    valid_until = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        # Check if discount is valid by time
        valid_by_time = self.valid_until is None or self.valid_until > timezone.now()
        print(f"Discount valid by time: {valid_by_time}")

        # Check if the user has sufficient likes for the discount
        total_likes = self.calculate_total_likes()
        valid_by_likes = total_likes >= 2  # Threshold for likes (e.g., 200 likes)
        print(f"Total likes: {total_likes}, valid by likes: {valid_by_likes}")

        return valid_by_time and valid_by_likes

    def calculate_total_likes(self):
        # Calculate the total likes across all posts by this user using aggregate for efficiency
        total_likes = Post.objects.filter(user=self.user).aggregate(
            total_likes=Sum('likes__count')
        )['total_likes'] or 0
        return total_likes

    def apply_discount(self, price):
        if self.is_valid():
            return price * (1 - self.discount_percentage / 100)
        return price
    
# Create your models here.

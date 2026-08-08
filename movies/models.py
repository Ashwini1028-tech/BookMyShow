from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from datetime import timedelta

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class CastMember(models.Model):
    name = models.CharField(max_length=150)
    photo = models.ImageField(upload_to="cast/", blank=True, null=True)

    def __str__(self):
        return self.name
class Movie(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3, decimal_places=1)
    description = models.TextField(blank=True, null=True)

    genre = models.ForeignKey(
        Genre,
        on_delete=models.SET_NULL,
        null=True
    )

    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True
    )

    cast = models.ManyToManyField(
        CastMember,
        blank=True
    )

    release_date = models.DateField(default="2025-01-01")
    popularity = models.PositiveIntegerField(default=0)
    ticket_price = models.DecimalField(max_digits=6, decimal_places=2, default=200.00)

    # 👇 Paste these here
    youtube_trailer = models.URLField(blank=True)

    age_certificate = models.CharField(
        max_length=20,
        default="U/A"
    )

    duration = models.PositiveIntegerField(
        default=120,
        help_text="Duration in minutes"
    )

    def __str__(self):
        return self.name
   

class Theater(models.Model):
    name = models.CharField(max_length=255)
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='theaters'
    )
    city = models.CharField(max_length=100, default="Bengaluru")
    time = models.DateTimeField()

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'

class Seat(models.Model):
    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='seats'
    )

    seat_number = models.CharField(
        max_length=10
    )

    is_booked = models.BooleanField(
        default=False
    )

    is_reserved = models.BooleanField(
        default=False
    )

    reserved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'

    def release_if_expired(self):
        if (
            self.is_reserved
            and self.reserved_at
            and timezone.now() >= self.reserved_at + timedelta(minutes=2)
        ):
            self.is_reserved = False
            self.reserved_at = None

            self.save(
                update_fields=[
                    "is_reserved",
                    "reserved_at"
                ]
            )

            return True

        return False




class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seat = models.OneToOneField(Seat, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)

    booking_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    payment_reference = models.CharField(
    max_length=100,
    blank=True,
    default="SUCCESS"
    ) 
    status = models.CharField(
    max_length=20,
    choices=[
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ],
    default="confirmed"
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True
    )

    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    refund_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    

    booked_at = models.DateTimeField(auto_now_add=True)
    class Meta:
       indexes = [
        models.Index(
            fields=["booked_at"]
        ),
        models.Index(
            fields=["status"]
        ),
        models.Index(
            fields=["movie"]
        ),
        models.Index(
            fields=["theater"]
        ),
        models.Index(
            fields=["user"]
        ),
        models.Index(
            fields=["status", "booked_at"]
        ),
    ]

    def __str__(self):
        return f"{self.booking_id} - {self.user.username}"

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("created", "Created"),
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    razorpay_order_id = models.CharField(
        max_length=100,
        unique=True
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    razorpay_signature = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="created"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.razorpay_order_id} - {self.status}"

class PaymentSeat(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="payment_seats"
    )

    seat = models.ForeignKey(
        Seat,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = ("payment", "seat")

    def __str__(self):
        return f"{self.payment.razorpay_order_id} - {self.seat.seat_number}"
class MoviePoster(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="posters"
    )
    
    image = models.ImageField(upload_to="movie_posters/")
    
    def __str__(self):
            return self.movie.name

class Review(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="reviews"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    rating = models.PositiveIntegerField()

    comment = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    reported = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    is_reported = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.movie.name} - {self.user.username}"
    
from django.urls import path
from . import views
from .views import export_bookings_csv
urlpatterns = [
    path('', views.movie_list, name='movie_list'),
    path(
    "<int:movie_id>/",
    views.movie_detail,
    name="movie_detail",
    ),
    path('<int:movie_id>/theaters', views.theater_list, name='theater_list'),
    path('theater/<int:theater_id>/seats/book/', views.book_seats, name='book_seats'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path(
    "admin/export-bookings/",
    export_bookings_csv,
    name="export_bookings_csv"
    ),
    path(
    "booking-history/",
    views.booking_history,
    name="booking_history"
    ),
   
    path(
    "download-ticket/<uuid:booking_id>/",
    views.download_ticket,
    name="download_ticket"
    ),
    path(
    "email-ticket/<uuid:booking_id>/",
    views.email_ticket,
    name="email_ticket"
    ),
    path(
    "movie/<int:movie_id>/review/",
    views.submit_review,
    name="submit_review",
    ),
    path(
    "review/<int:review_id>/edit/",
    views.edit_review,
    name="edit_review",
    ),
    path(
    "review/<int:review_id>/report/",
    views.report_review,
    name="report_review",
    ),
    path(
    "payment/<int:payment_id>/",
    views.payment_page,
    name="payment_page",
    ),
    path(
    "payment-success/",
    views.payment_success,
    name="payment_success",
    ),
    path(
    "payment-cancelled/<int:payment_id>/",
    views.payment_cancelled,
    name="payment_cancelled",
    ),
    path(
    "payment-failed/<int:payment_id>/",
    views.payment_failed,
    name="payment_failed",
    ),

    path(
    "payment-retry/<int:payment_id>/",
    views.retry_payment,
    name="retry_payment",
    ),
    path(
    "razorpay/webhook/",
    views.razorpay_webhook,
    name="razorpay_webhook",
    ),
    path(
    "theater/<int:theater_id>/availability/",
    views.seat_availability,
    name="seat_availability",
    ),
]
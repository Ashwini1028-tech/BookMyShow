from django.shortcuts import render, redirect, get_object_or_404
from .models import Movie, Theater, Seat, Booking
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import ExtractHour
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.contrib.auth.models import User
from django.utils.dateparse import parse_date
import csv
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.http import HttpResponse
import qrcode
import io
from django.core.mail import send_mail

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Image,
)
from django.core.mail import EmailMessage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from .tasks import send_booking_email
from .models import (
    Movie,
    Theater,
    Seat,
    Booking,
    Genre,
    Language,
    CastMember,
    MoviePoster,
    Review,
    Payment,
    PaymentSeat,
)
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg
import razorpay
from django.conf import settings
from django.utils import timezone
from django.db import transaction
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.pagesizes import A4

razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET
    )
)
def movie_list(request):

    movies = Movie.objects.all().order_by('id')

    # Search
    search = request.GET.get('search')
    if search:
        movies = movies.filter(name__icontains=search)

    # Genre Filter
    genre = request.GET.get('genre')
    if genre:
        movies = movies.filter(genre__name=genre)

    # Language Filter
    language = request.GET.get('language')
    if language:
        movies = movies.filter(language__name=language)

    # City Filter
    city = request.GET.get('city')
    if city:
        movies = movies.filter(theaters__city=city).distinct()

    theater = request.GET.get('theater')
    if theater:
        movies = movies.filter(theaters__name=theater).distinct()

    # Rating Filter
    rating = request.GET.get('rating')
    if rating:
        movies = movies.filter(rating__gte=rating)

    # Release Date Filter
    release_date = request.GET.get('release_date')
    if release_date:
        movies = movies.filter(release_date=release_date)
    show_date = request.GET.get('show_date')

    if show_date:
        movies = movies.filter(theaters__time__date=show_date).distinct()
    # Sorting
    sort = request.GET.get('sort')

    if sort == 'popularity':
        movies = movies.order_by('-popularity')

    elif sort == 'rating':
        movies = movies.order_by('-rating')

    elif sort == 'newest':
        movies = movies.order_by('-release_date')

    elif sort == 'price':
        movies = movies.order_by('ticket_price')

    # Pagination
    paginator = Paginator(movies, 8)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)
    theaters = Theater.objects.all()
    show_dates = Theater.objects.values_list(
        'time__date',
         flat=True
    ).distinct()

    recommended_movies = []

    if request.user.is_authenticated:
        booked_movie_ids = Booking.objects.filter(
            user=request.user
        ).values_list('movie_id', flat=True)

        recommended_movies = Movie.objects.exclude(
            id__in=booked_movie_ids
        ).order_by('-rating')[:4]

    genres = Genre.objects.all()
    languages = Language.objects.all()

    context = {
        "movies": page_obj,
        "page_obj": page_obj,
        "movie_count": movies.count(),
        "theaters": theaters,
        "show_dates": show_dates,
        "recommended_movies": recommended_movies,
        "genres": genres,
        "languages": languages,
    }

    return render(request, "movies/movie_list.html", context)

def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    similar_movies = Movie.objects.filter(
        genre=movie.genre,
        language=movie.language
    ).exclude(id=movie.id)[:4]

    trending_movies = Movie.objects.order_by(
        "-popularity"
    )[:4]

    recent_movies = Movie.objects.order_by(
        "-release_date"
    )[:4]

    reviews = Review.objects.filter(
        movie=movie
    ).select_related("user").order_by("-created_at")

    has_booked = False

    if request.user.is_authenticated:
        has_booked = Booking.objects.filter(
            user=request.user,
            movie=movie
        ).exists()

    context = {
        "movie": movie,
        "similar_movies": similar_movies,
        "trending_movies": trending_movies,
        "recent_movies": recent_movies,
        "reviews": reviews,
        "has_booked": has_booked,
    }

    return render(
        request,
        "movies/movie_detail.html",
        context
    )

@login_required
def submit_review(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    has_booked = Booking.objects.filter(
        user=request.user,
        movie=movie
    ).exists()

    if not has_booked:
        messages.error(
            request,
            "You can review this movie only after booking it."
        )
        return redirect("movie_detail", movie_id=movie.id)

    if request.method == "POST":

        rating = request.POST.get("rating")
        comment = request.POST.get("comment")

        if not rating or not comment:
            messages.error(
                request,
                "Please provide both rating and review."
            )
            return redirect("movie_detail", movie_id=movie.id)

        Review.objects.create(
            movie=movie,
            user=request.user,
            rating=rating,
            comment=comment
        )

        average_rating = Review.objects.filter(
            movie=movie
        ).aggregate(
            average=Avg("rating")
        )["average"]

        if average_rating is not None:
            movie.rating = round(average_rating, 1)
            movie.save(update_fields=["rating"])

        messages.success(
            request,
            "Your review has been submitted successfully!"
        )

    return redirect("movie_detail", movie_id=movie.id)
@login_required
def edit_review(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id,
        user=request.user
    )

    if request.method == "POST":

        rating = request.POST.get("rating")
        comment = request.POST.get("comment")

        if not rating or not comment:
            messages.error(
                request,
                "Please provide both rating and review."
            )

            return redirect(
                "edit_review",
                review_id=review.id
            )

        review.rating = rating
        review.comment = comment
        review.save()

        average_rating = Review.objects.filter(
            movie=review.movie
        ).aggregate(
            average=Avg("rating")
        )["average"]

        if average_rating is not None:
            review.movie.rating = round(
                average_rating,
                1
            )

            review.movie.save(
                update_fields=["rating"]
            )

        messages.success(
            request,
            "Your review has been updated successfully!"
        )

        return redirect(
            "movie_detail",
            movie_id=review.movie.id
        )

    return render(
        request,
        "movies/edit_review.html",
        {
            "review": review
        }
    )

@login_required
def report_review(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id
    )

    review.reported = True
    review.save(update_fields=["reported"])

    messages.success(
        request,
        "Thank you. This review has been reported."
    )

    return redirect(
        "movie_detail",
        movie_id=review.movie.id
    )
def theater_list(request,movie_id):
    movie = get_object_or_404(Movie,id=movie_id)
    theater=Theater.objects.filter(movie=movie)
    return render(request,'movies/theater_list.html',{'movie':movie,'theaters':theater})
from io import BytesIO
import qrcode
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Image,
)



def generate_ticket_pdf(booking):
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph("<b>BookMySeat Movie Ticket</b>", styles["Title"])
    )

    data = [
        ["Booking ID", str(booking.booking_id)],
        ["Movie", booking.movie.name],
        ["Theater", booking.theater.name],
        ["City", booking.theater.city],
        ["Seat", booking.seat.seat_number],
        ["Show Time", str(booking.theater.time)],
        ["Payment", booking.payment_reference],
    ]

    table = Table(data)

    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.darkblue),
        ("TEXTCOLOR", (0,0), (0,-1), colors.white),
    ]))

    elements.append(table)

    qr = qrcode.make(
        f"Booking:{booking.booking_id}"
    )

    qr_buffer = BytesIO()

    qr.save(qr_buffer)

    qr_buffer.seek(0)

    elements.append(
        Image(qr_buffer, width=120, height=120)
    )

    doc.build(elements)

    pdf = buffer.getvalue()

    buffer.close()

    return pdf



@login_required(login_url='/login/')
def book_seats(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    seats = Seat.objects.filter(
        theater=theater
    )

    # Release expired 2-minute reservations
    for seat in seats:
        seat.release_if_expired()

    # -----------------------------
    # GET REQUEST
    # -----------------------------
    if request.method != "POST":
        return render(
            request,
            "movies/seat_selection.html",
            {
                "theaters": theater,
                "seats": seats
            }
        )

    # -----------------------------
    # POST REQUEST
    # -----------------------------
    selected_seats = request.POST.getlist("seats")

    if not selected_seats:
        return render(
            request,
            "movies/seat_selection.html",
            {
                "theaters": theater,
                "seats": seats,
                "error": "No seat selected"
            }
        )

    selected_seat_objects = []

    try:

        with transaction.atomic():

            # Lock and check every selected seat
            for seat_id in selected_seats:

                seat = Seat.objects.select_for_update().get(
                    id=seat_id,
                    theater=theater
                )

                # Release expired reservation
                if (
                    seat.is_reserved
                    and seat.reserved_at
                    and timezone.now() >= (
                        seat.reserved_at +
                        timedelta(minutes=2)
                    )
                ):
                    seat.is_reserved = False
                    seat.reserved_at = None

                    seat.save(
                        update_fields=[
                            "is_reserved",
                            "reserved_at"
                        ]
                    )

                # Check whether seat is available
                if seat.is_booked or seat.is_reserved:

                    raise ValueError(
                        f"Seat {seat.seat_number} is no longer available."
                    )

                selected_seat_objects.append(seat)

            # -----------------------------
            # TEMPORARILY RESERVE SEATS
            # -----------------------------
            for seat in selected_seat_objects:

                seat.is_reserved = True
                seat.reserved_at = timezone.now()

                seat.save(
                    update_fields=[
                        "is_reserved",
                        "reserved_at"
                    ]
                )

            # -----------------------------
            # CALCULATE PAYMENT
            # -----------------------------
            total_amount = (
                theater.movie.ticket_price *
                len(selected_seat_objects)
            )

            amount_paise = int(
                total_amount * 100
            )

            print("Ticket price:", theater.movie.ticket_price)
            print("Selected seats:", len(selected_seat_objects))
            print("Total amount:", total_amount)
            print("Razorpay amount:", amount_paise)

            # -----------------------------
            # CREATE RAZORPAY ORDER
            # -----------------------------
            razorpay_order = razorpay_client.order.create(
                {
                    "amount": amount_paise,
                    "currency": "INR",
                    "payment_capture": 1
                }
            )

            # -----------------------------
            # CREATE PAYMENT RECORD
            # -----------------------------
            payment = Payment.objects.create(
                user=request.user,
                movie=theater.movie,
                theater=theater,
                amount=total_amount,
                razorpay_order_id=razorpay_order["id"],
                status="created"
            )

            # -----------------------------
            # SAVE SELECTED SEATS
            # -----------------------------
            for seat in selected_seat_objects:

                PaymentSeat.objects.create(
                    payment=payment,
                    seat=seat
                )

    except ValueError as e:

        return render(
            request,
            "movies/seat_selection.html",
            {
                "theaters": theater,
                "seats": seats,
                "error": str(e)
            }
        )

    except Exception as e:

        print("Payment order error:", e)

        return render(
            request,
            "movies/seat_selection.html",
            {
                "theaters": theater,
                "seats": seats,
                "error": "Unable to start payment. Please try again."
            }
        )

    # -----------------------------
    # GO TO PAYMENT PAGE
    # -----------------------------
    return redirect(
        "payment_page",
        payment_id=payment.id
    )
@login_required(login_url='/login/')
def seat_availability(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    seats = Seat.objects.filter(
        theater=theater
    )

    # Release expired reservations
    for seat in seats:
        seat.release_if_expired()

    seats_data = []

    for seat in seats:

        if seat.is_booked:
            status = "booked"

        elif seat.is_reserved:
            status = "reserved"

        else:
            status = "available"

        seats_data.append({
            "id": seat.id,
            "seat_number": seat.seat_number,
            "status": status,
        })

    return JsonResponse({
        "seats": seats_data
    })





@staff_member_required
def admin_dashboard(request):

    # Date filter
    # Date filter
    # --------------------------------
# Date Filter
# --------------------------------

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    bookings = Booking.objects.all()

    if start_date:
        start_date = parse_date(start_date)

        if start_date:
            bookings = bookings.filter(
            booked_at__date__gte=start_date
            )

    if end_date:
        end_date = parse_date(end_date)

        if end_date:
            bookings = bookings.filter(
            booked_at__date__lte=end_date
            )
    # Basic counts
    total_movies = Movie.objects.count()

    total_theaters = Theater.objects.count()

    total_bookings = bookings.count()


    # --------------------------------
# Revenue Reports
# --------------------------------

# Revenue for the selected date range
    total_revenue = (
        bookings
        .aggregate(
            total=Sum("movie__ticket_price")
        )["total"]
        or 0
    )

    today = timezone.now().date()

# Use a separate queryset for fixed-period reports
    all_bookings = Booking.objects.all()

# Daily revenue
    daily_revenue = (
        all_bookings
        .filter(
            booked_at__date=today
        )
        .aggregate(
            total=Sum("movie__ticket_price")
        )["total"]
        or 0
    )

# Weekly revenue
    week_start = today - timedelta(days=6)

    weekly_revenue = (
        all_bookings
        .filter(
            booked_at__date__range=[
                week_start,
                today
            ]
        )
        .aggregate(
            total=Sum("movie__ticket_price")
        )["total"]
        or 0
    )

# Monthly revenue
    monthly_revenue = (
        all_bookings
        .filter(
            booked_at__year=today.year,
            booked_at__month=today.month
        )
        .aggregate(
            total=Sum("movie__ticket_price")
        )["total"]
        or 0
    )

# Yearly revenue
    yearly_revenue = (
        all_bookings
        .filter(
            booked_at__year=today.year
        )
        .aggregate(
            total=Sum("movie__ticket_price")
        )["total"]
        or 0
    )
    # --------------------------------
# Theater Occupancy
# --------------------------------


    theater_occupancy = (
        Theater.objects
        .annotate(
            total_seats=Count("seats", distinct=True),
            booked_seats=Count(
                "seats",
                filter=Q(seats__is_booked=True),
                distinct=True
            )
        )
        .values(
            "name",
            "movie__name",
            "city",
            "total_seats",
            "booked_seats"
        )
    )

    occupancy_data = []

    for theater in theater_occupancy:

        total_seats = theater["total_seats"]
        booked_seats = theater["booked_seats"]

        if total_seats > 0:
            occupancy = round(
                (booked_seats / total_seats) * 100,
                2
            )
        else:
            occupancy = 0

        occupancy_data.append({
            "name": theater["name"],
            "movie": theater["movie__name"],
            "city": theater["city"],
            "total_seats": total_seats,
            "booked_seats": booked_seats,
            "occupancy": occupancy,
        })


    # --------------------------------
# Most Booked Movies
# --------------------------------

    most_booked_movies = (
        bookings
        .values(
            "movie_id",
            "movie__name"
        )
        .annotate(
            total_bookings=Count("id")
        )
        .order_by("-total_bookings")[:5]
    )


# --------------------------------
# Top Performing Theaters
# --------------------------------

    top_theaters = (
        bookings
        .values(
            "theater_id",
            "theater__name",
            "theater__city"
        )
        .annotate(
            total_bookings=Count("id")
        )
        .order_by("-total_bookings")[:5]
    )


# --------------------------------
# Peak Booking Hours
# --------------------------------

    peak_booking_hours = (
        bookings
        .annotate(
            hour=ExtractHour("booked_at")
        )
        .values("hour")
        .annotate(
            total_bookings=Count("id")
        )
        .order_by("-total_bookings")
    )
    # --------------------------------
# Cancellation & Refund Statistics
# --------------------------------

    cancelled_bookings = (
        bookings
        .filter(status="cancelled")
        .count()
    )

    refunded_bookings = (
        bookings
        .filter(status="refunded")
        .count()
    )

    total_refund_amount = (
        bookings
        .filter(status="refunded")
        .aggregate(
            total=Sum("refund_amount")
        )["total"]
        or 0
    )

    # --------------------------------
# User Growth Report
# --------------------------------

    # --------------------------------
# User Growth Report
# --------------------------------

    user_growth_queryset = User.objects.all()

    if start_date:
        user_growth_queryset = user_growth_queryset.filter(
            date_joined__date__gte=start_date
        )

    if end_date:
        user_growth_queryset = user_growth_queryset.filter(
            date_joined__date__lte=end_date
        )

    user_growth = (
        user_growth_queryset
        .annotate(
            date=TruncDate("date_joined")
        )
       .values("date")
       .annotate(
            total_users=Count("id")
        )
        .order_by("date")
    )


    context = {

        "total_movies": total_movies,

        "total_theaters": total_theaters,

        "total_bookings": total_bookings,

        "total_revenue": total_revenue,

        "daily_revenue": daily_revenue,

        "weekly_revenue": weekly_revenue,

        "monthly_revenue": monthly_revenue,

        "yearly_revenue": yearly_revenue,

        "theater_occupancy": occupancy_data,

        "most_booked_movies": most_booked_movies,

        "top_theaters": top_theaters,

        "peak_booking_hours": peak_booking_hours,

        "user_growth": user_growth,

        "start_date": start_date,

        "end_date": end_date,
        "cancelled_bookings": cancelled_bookings,

        "refunded_bookings": refunded_bookings,

        "total_refund_amount": total_refund_amount,

    }


    return render(
        request,
        "movies/admin_dashboard.html",
        context
    )
@staff_member_required
def export_bookings_csv(request):

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    bookings = Booking.objects.select_related(
        "user",
        "movie",
        "theater",
        "seat"
    ).all()

    if start_date:
        start_date = parse_date(start_date)

        if start_date:
            bookings = bookings.filter(
                booked_at__date__gte=start_date
            )

    if end_date:
        end_date = parse_date(end_date)

        if end_date:
            bookings = bookings.filter(
                booked_at__date__lte=end_date
            )

    response = HttpResponse(
        content_type="text/csv"
    )

    response["Content-Disposition"] = (
        'attachment; filename="bookings_report.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        "Booking ID",
        "User",
        "Movie",
        "Theater",
        "City",
        "Seat",
        "Booking Date",
        "Status",
        "Amount",
        "Payment Reference",
        "Refund Amount",
        "Refund Reference",
    ])

    for booking in bookings.iterator():

        writer.writerow([
            str(booking.booking_id),
            booking.user.username,
            booking.movie.name,
            booking.theater.name,
            booking.theater.city,
            booking.seat.seat_number,
            booking.booked_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            booking.status,
            booking.movie.ticket_price,
            booking.payment_reference,
            booking.refund_amount,
            booking.refund_reference or "",
        ])

    return response




@login_required
def booking_history(request):
    print("Current User:", request.user.id, request.user.username)

    bookings = (
        Booking.objects
        .filter(user=request.user)
        .select_related("movie", "theater", "seat")
        .order_by("-booked_at")
    )

    print("Bookings Found:", bookings.count())

    return render(request, "movies/booking_history.html", {
        "bookings": bookings
    })
@login_required
def download_ticket(request, booking_id):

    booking = get_object_or_404(
        Booking,
        booking_id=booking_id,
        user=request.user
    )

    response = HttpResponse(content_type='application/pdf')

    response['Content-Disposition'] = (
        f'attachment; filename="Ticket_{booking.booking_id}.pdf"'
    )

    doc = SimpleDocTemplate(response)

    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph(
    "<font size=22 color='darkblue'><b>🎬 BookMySeat Movie Ticket</b></font>",
    styles["Title"]
    ))

    elements.append(Paragraph("<br/>", styles["Normal"]))
    elements.append(
    Paragraph("<b>Booking Details</b>", styles["Heading2"])
    )

    data = [
        ["Booking ID", str(booking.booking_id)],
        ["Movie", booking.movie.name],
        ["Theater", booking.theater.name],
        ["City", booking.theater.city],
        ["Seat", booking.seat.seat_number],
        ["Show Time", str(booking.theater.time)],
        ["Booked At", str(booking.booked_at)],
        ["Payment", booking.payment_reference],
    ]

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.beige),
        ("BACKGROUND", (0,0), (0,-1), colors.darkblue),
        ("TEXTCOLOR", (0,0), (0,-1), colors.white),
        ("GRID", (0,0), (-1,-1), 1, colors.grey),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
    ]))

    elements.append(table)
    # Generate QR Code
    qr_data = f"""
    Booking ID: {booking.booking_id}
    Movie: {booking.movie.name}
    Theater: {booking.theater.name}
    Seat: {booking.seat.seat_number}
    Show Time: {booking.theater.time}
    """

    qr = qrcode.make(qr_data)

    buffer = io.BytesIO()

    qr.save(buffer)

    buffer.seek(0)

    elements.append(Paragraph("<br/><b>QR Code</b>", styles["Heading2"]))

    elements.append(Image(buffer, width=120, height=120))
    elements.append(Paragraph("<br/>", styles["Normal"]))

    elements.append(
        Paragraph(
            "<b>Thank you for booking with BookMySeat!</b>",
            styles["Heading2"]
        )
    )

    elements.append(
        Paragraph(
            "Please carry this ticket and present the QR code at the theater entrance.",
            styles["Normal"]
        )
    )

    doc.build(elements)


    return response

@login_required
def email_ticket(request, booking_id):

    booking = get_object_or_404(
        Booking.objects.select_related(
            "movie",
            "theater",
            "seat",
            "user"
        ),
        booking_id=booking_id,
        user=request.user
    )

    # Make sure the user has an email address
    recipient_email = request.user.email

    if not recipient_email:
        messages.error(
            request,
            "No email address is associated with your account."
        )
        return redirect("booking_history")

    # =====================================================
    # GENERATE PDF
    # =====================================================

    pdf_buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    elements = []

    title_style = ParagraphStyle(
        "TicketTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.darkblue,
        spaceAfter=20
    )

    heading_style = ParagraphStyle(
        "TicketHeading",
        parent=styles["Heading2"],
        textColor=colors.darkblue,
        spaceBefore=15,
        spaceAfter=10
    )

    elements.append(
        Paragraph(
            "BookMySeat Movie Ticket",
            title_style
        )
    )

    elements.append(
        Paragraph(
            "Booking Details",
            heading_style
        )
    )

    data = [
        ["Booking ID", str(booking.booking_id)],
        ["Movie", booking.movie.name],
        ["Theater", booking.theater.name],
        ["City", booking.theater.city],
        ["Seat", booking.seat.seat_number],
        ["Show Time", str(booking.theater.time)],
        ["Booked At", str(booking.booked_at)],
        ["Payment", str(booking.payment_reference)],
    ]

    table = Table(
        data,
        colWidths=[120, 350]
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.darkblue
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (0, -1),
                colors.white
            ),
            (
                "BACKGROUND",
                (1, 0),
                (1, -1),
                colors.whitesmoke
            ),
            (
                "TEXTCOLOR",
                (1, 0),
                (1, -1),
                colors.black
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                1,
                colors.grey
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, -1),
                "Helvetica"
            ),
            (
                "FONTNAME",
                (0, 0),
                (0, -1),
                "Helvetica-Bold"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                8
            ),
        ])
    )

    elements.append(table)

    # =====================================================
    # QR CODE
    # =====================================================

    qr_data = f"""
    Booking ID: {booking.booking_id}
    Movie: {booking.movie.name}
    Theater: {booking.theater.name}
    Seat: {booking.seat.seat_number}
    Show Time: {booking.theater.time}
    """

    qr = qrcode.make(qr_data)

    qr_buffer = io.BytesIO()

    qr.save(
        qr_buffer,
        format="PNG"
    )

    qr_buffer.seek(0)

    elements.append(
        Paragraph(
            "QR Code",
            heading_style
        )
    )

    elements.append(
        Image(
            qr_buffer,
            width=120,
            height=120
        )
    )

    elements.append(
        Paragraph(
            "<br/><b>Thank you for booking with BookMySeat!</b>",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            "Please carry this ticket and present the QR code "
            "at the theater entrance.",
            styles["Normal"]
        )
    )

    # Build PDF
    doc.build(elements)

    pdf_buffer.seek(0)

    # =====================================================
    # SEND EMAIL
    # =====================================================

    email = EmailMessage(
        subject=(
            f"BookMySeat Ticket - "
            f"Booking #{booking.booking_id}"
        ),

        body=f"""
Hello {request.user.username},

Your BookMySeat ticket has been confirmed successfully.

Movie: {booking.movie.name}
Theater: {booking.theater.name}
City: {booking.theater.city}
Seat: {booking.seat.seat_number}
Show Time: {booking.theater.time}

Booking ID:
{booking.booking_id}

Your ticket PDF is attached to this email.

Thank you for using BookMySeat!

Regards,
BookMySeat Team
""",

        from_email=settings.DEFAULT_FROM_EMAIL,

        to=[
            recipient_email
        ],
    )

    email.attach(
        f"Ticket_{booking.booking_id}.pdf",
        pdf_buffer.getvalue(),
        "application/pdf"
    )

    try:

        result = email.send(
            fail_silently=False
        )

        print(
            "EMAIL SEND RESULT:",
            result
        )

        messages.success(
            request,
            "🎉 Ticket has been sent successfully to your email!"
        )

    except Exception as e:

        print("=" * 60)
        print("EMAIL TICKET ERROR:")
        print(repr(e))
        print("=" * 60)

        messages.error(
            request,
            "Unable to send the ticket email. Please try again."
        )

    finally:

        pdf_buffer.close()
        qr_buffer.close()

    return redirect("booking_history")

@login_required
def create_payment(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    amount = theater.movie.ticket_price

    amount_paise = int(
        amount * 100
    )

    razorpay_order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    payment = Payment.objects.create(
        user=request.user,
        movie=theater.movie,
        theater=theater,
        amount=amount,
        razorpay_order_id=razorpay_order["id"],
        status="created"
    )

    context = {
        "payment": payment,
        "theater": theater,
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "razorpay_amount": amount_paise,
    }

    return render(
        request,
        "movies/payment.html",
        context
    )


@login_required(login_url="/login/")
def payment_success(request):

    payment_id = request.GET.get("payment_id")
    order_id = request.GET.get("order_id")
    signature = request.GET.get("signature")

    if not payment_id or not order_id or not signature:

        messages.error(
            request,
            "Invalid payment response."
        )

        return redirect("movie_list")

    payment = get_object_or_404(
        Payment,
        razorpay_order_id=order_id,
        user=request.user
    )

    # Prevent duplicate processing
    if payment.status == "success":

        messages.info(
            request,
            "This payment has already been processed."
        )

        return redirect("booking_history")

    try:

        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })

    except razorpay.errors.SignatureVerificationError:

        payment.status = "failed"

        payment.save(
            update_fields=["status"]
        )

        payment_seats = PaymentSeat.objects.filter(
            payment=payment
        ).select_related("seat")

        for payment_seat in payment_seats:

            seat = payment_seat.seat

            if not seat.is_booked:

                seat.is_reserved = False
                seat.reserved_at = None

                seat.save(
                    update_fields=[
                        "is_reserved",
                        "reserved_at"
                    ]
                )

        messages.error(
            request,
            "Payment verification failed."
        )

        return redirect(
            "movie_detail",
            movie_id=payment.movie.id
        )

    # Payment verified successfully
    with transaction.atomic():

        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.status = "success"

        payment.save()

        payment_seats = PaymentSeat.objects.filter(
            payment=payment
        ).select_related("seat")

        for payment_seat in payment_seats:

            seat = payment_seat.seat

            # Prevent duplicate booking
            Booking.objects.get_or_create(
                seat=seat,
                defaults={
                    "user": request.user,
                    "movie": payment.movie,
                    "theater": payment.theater,
                    "payment_reference": payment_id,
                }
            )

            seat.is_booked = True
            seat.is_reserved = False
            seat.reserved_at = None

            seat.save(
                update_fields=[
                    "is_booked",
                    "is_reserved",
                    "reserved_at"
                ]
            )

    messages.success(
        request,
        "Payment successful! Your tickets are confirmed."
    )

    return redirect("booking_history")


@login_required(login_url="/login/")
def payment_cancelled(request, payment_id):

    payment = get_object_or_404(
        Payment,
        id=payment_id,
        user=request.user
    )

    # Don't modify successful payment
    if payment.status == "success":

        messages.info(
            request,
            "This payment has already been completed."
        )

        return redirect("booking_history")

    payment.status = "cancelled"

    payment.save(
        update_fields=["status"]
    )

    payment_seats = PaymentSeat.objects.filter(
        payment=payment
    ).select_related("seat")

    for payment_seat in payment_seats:

        seat = payment_seat.seat

        if not seat.is_booked:

            seat.is_reserved = False
            seat.reserved_at = None

            seat.save(
                update_fields=[
                    "is_reserved",
                    "reserved_at"
                ]
            )

    messages.warning(
        request,
        "Payment was cancelled. Your seats have been released."
    )

    return redirect("movie_list")


@login_required(login_url="/login/")
def payment_failed(request, payment_id):

    payment = get_object_or_404(
        Payment,
        id=payment_id,
        user=request.user
    )

    # Never change successful payment
    if payment.status == "success":

        messages.info(
            request,
            "This payment has already been completed."
        )

        return redirect("booking_history")

    payment.status = "failed"

    payment.save(
        update_fields=["status"]
    )

    # Release reserved seats
    payment_seats = PaymentSeat.objects.filter(
        payment=payment
    ).select_related("seat")

    for payment_seat in payment_seats:

        seat = payment_seat.seat

        if not seat.is_booked:

            seat.is_reserved = False
            seat.reserved_at = None

            seat.save(
                update_fields=[
                    "is_reserved",
                    "reserved_at"
                ]
            )

    messages.error(
        request,
        "Payment failed. Your seats have been released."
    )

    return redirect(
        "movie_detail",
        movie_id=payment.movie.id
    )


@login_required(login_url="/login/")
def retry_payment(request, payment_id):

    payment = get_object_or_404(
        Payment,
        id=payment_id,
        user=request.user
    )

    # Already successful
    if payment.status == "success":

        messages.info(
            request,
            "This payment has already been completed."
        )

        return redirect("booking_history")

    payment_seats = PaymentSeat.objects.filter(
        payment=payment
    ).select_related("seat")

    if not payment_seats.exists():

        messages.error(
            request,
            "No seats are available for this payment."
        )

        return redirect(
            "movie_detail",
            movie_id=payment.movie.id
        )

    try:

        with transaction.atomic():

            # Lock seats
            for payment_seat in payment_seats:

                seat = Seat.objects.select_for_update().get(
                    id=payment_seat.seat.id
                )

                # Don't allow retry if seat is already booked
                if seat.is_booked:

                    messages.error(
                        request,
                        f"Seat {seat.seat_number} has already been booked."
                    )

                    return redirect(
                        "movie_detail",
                        movie_id=payment.movie.id
                    )

                seat.is_reserved = True
                seat.reserved_at = timezone.now()

                seat.save(
                    update_fields=[
                        "is_reserved",
                        "reserved_at"
                    ]
                )

            amount_paise = int(
                payment.amount * 100
            )

            # Create new Razorpay order
            razorpay_order = razorpay_client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "payment_capture": 1
            })

            payment.razorpay_order_id = razorpay_order["id"]
            payment.razorpay_payment_id = None
            payment.razorpay_signature = None
            payment.status = "created"

            payment.save()

    except Exception as e:

        print(
            "Retry payment error:",
            e
        )

        messages.error(
            request,
            "Unable to retry payment. Please try again."
        )

        return redirect(
            "movie_detail",
            movie_id=payment.movie.id
        )

    return redirect(
        "payment_page",
        payment_id=payment.id
    )


@login_required(login_url="/login/")
def payment_page(request, payment_id):

    payment = get_object_or_404(
        Payment,
        id=payment_id,
        user=request.user
    )

    context = {
        "payment": payment,
        "theater": payment.theater,
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "razorpay_amount": int(
            payment.amount * 100
        ),
    }

    return render(
        request,
        "movies/payment.html",
        context
    )


@csrf_exempt
def razorpay_webhook(request):

    if request.method != "POST":

        return JsonResponse(
            {"status": "method not allowed"},
            status=405
        )

    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET

    received_signature = request.headers.get(
        "X-Razorpay-Signature"
    )

    if not received_signature:

        return JsonResponse(
            {"status": "missing signature"},
            status=400
        )

    try:

        razorpay_client.utility.verify_webhook_signature(
            request.body.decode("utf-8"),
            received_signature,
            webhook_secret
        )

    except razorpay.errors.SignatureVerificationError:

        return JsonResponse(
            {"status": "invalid signature"},
            status=400
        )

    try:

        data = json.loads(
            request.body.decode("utf-8")
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {"status": "invalid json"},
            status=400
        )

    event = data.get("event")

    # =====================================================
    # PAYMENT CAPTURED
    # =====================================================

    if event == "payment.captured":

        payment_entity = data[
            "payload"
        ][
            "payment"
        ][
            "entity"
        ]

        order_id = payment_entity.get(
            "order_id"
        )

        payment_id = payment_entity.get(
            "id"
        )

        payment = Payment.objects.filter(
            razorpay_order_id=order_id
        ).first()

        if payment:

            # Mark payment successful
            if payment.status != "success":

                payment.razorpay_payment_id = payment_id
                payment.status = "success"

                payment.save(
                    update_fields=[
                        "razorpay_payment_id",
                        "status",
                        "updated_at"
                    ]
                )

            # IMPORTANT:
            # Booking creation is INSIDE the loop
            payment_seats = PaymentSeat.objects.filter(
                payment=payment
            ).select_related("seat")

            for payment_seat in payment_seats:

                seat = payment_seat.seat

                Booking.objects.get_or_create(
                    seat=seat,
                    defaults={
                        "user": payment.user,
                        "movie": payment.movie,
                        "theater": payment.theater,
                        "payment_reference": payment_id,
                    }
                )

                seat.is_booked = True
                seat.is_reserved = False
                seat.reserved_at = None

                seat.save(
                    update_fields=[
                        "is_booked",
                        "is_reserved",
                        "reserved_at"
                    ]
                )

    # =====================================================
    # PAYMENT FAILED
    # =====================================================

    elif event == "payment.failed":

        payment_entity = data[
            "payload"
        ][
            "payment"
        ][
            "entity"
        ]

        order_id = payment_entity.get(
            "order_id"
        )

        payment = Payment.objects.filter(
            razorpay_order_id=order_id
        ).first()

        if payment and payment.status != "success":

            payment.status = "failed"

            payment.save(
                update_fields=[
                    "status",
                    "updated_at"
                ]
            )

            payment_seats = PaymentSeat.objects.filter(
                payment=payment
            ).select_related("seat")

            for payment_seat in payment_seats:

                seat = payment_seat.seat

                if not seat.is_booked:

                    seat.is_reserved = False
                    seat.reserved_at = None

                    seat.save(
                        update_fields=[
                            "is_reserved",
                            "reserved_at"
                        ]
                    )

    return JsonResponse(
        {"status": "ok"}
    )
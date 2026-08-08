from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings

@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_booking_email(
    username,
    user_email,
    movie_name,
    theater_name,
    seat_number,
    booking_id,
    pdf_bytes,
):
    email = EmailMessage(
        subject="BookMySeat Ticket Confirmation",
        body=f"""
Hello {username},

Your ticket has been booked successfully.

Movie: {movie_name}
Theater: {theater_name}
Seat: {seat_number}

Your ticket is attached as a PDF.

Enjoy your movie!
""",
        from_email=settings.EMAIL_HOST_USER,
        to=[user_email],
    )

    email.attach(
        f"Ticket_{booking_id}.pdf",
        pdf_bytes,
        "application/pdf",
    )

    email.send()
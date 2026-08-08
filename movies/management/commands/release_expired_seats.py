from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from movies.models import Seat


class Command(BaseCommand):

    help = "Release seats whose 2-minute reservation has expired"

    def handle(self, *args, **kwargs):

        expiry_time = timezone.now() - timedelta(minutes=2)

        expired_seats = Seat.objects.filter(
            is_reserved=True,
            reserved_at__isnull=False,
            reserved_at__lte=expiry_time
        )

        count = expired_seats.update(
            is_reserved=False,
            reserved_at=None
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{count} expired seat reservation(s) released."
            )
        )
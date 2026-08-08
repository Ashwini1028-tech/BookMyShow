from django.contrib import admin
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
)
from django import forms
from .models import Movie, Theater, Seat, Booking, Review

class MoviePosterInline(admin.TabularInline):
    model = MoviePoster
    extra = 1


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "genre",
        "language",
        "rating",
        "age_certificate",
        "duration",
        "release_date",
        "ticket_price",
        "popularity",
    )

    search_fields = (
        "name",
    )

    list_filter = (
        "genre",
        "language",
        "release_date",
        "age_certificate",
    )

    filter_horizontal = ("cast",)

    inlines = [MoviePosterInline]


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(CastMember)
class CastMemberAdmin(admin.ModelAdmin):
    list_display = ("name",)
    
@admin.register(MoviePoster)
class MoviePosterAdmin(admin.ModelAdmin):
    list_display = (
        "movie",
        "image",
    )

class TheaterAdminForm(forms.ModelForm):

    class Meta:
        model = Theater
        fields = '__all__'

        widgets = {
            'time': forms.DateTimeInput(
                format='%Y-%m-%d %H:%M',
                attrs={
                    'type': 'datetime-local'
                }
            ),
        }

@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    form = TheaterAdminForm
    list_display = (
        'name',
        'movie',
        'city',
        'time',
    )

    search_fields = (
        'name',
        'city',
    )

    list_filter = (
        'city',
    )

    fields = (
        'name',
        'movie',
        'city',
        'time',
    )

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = (
        "theater",
        "seat_number",
        "is_booked",
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "movie",
        "theater",
        "seat",
        "booked_at",
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):

    list_display = (
        "movie",
        "user",
        "rating",
        "reported",
        "created_at",
    )

    list_filter = (
        "reported",
        "rating",
        "created_at",
    )

    search_fields = (
        "movie__name",
        "user__username",
        "comment",
    )
   
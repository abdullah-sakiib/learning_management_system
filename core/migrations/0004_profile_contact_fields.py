from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_alter_course_rating_alter_enrollment_progress_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="phone",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="profile",
            name="city",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="profile",
            name="country",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]

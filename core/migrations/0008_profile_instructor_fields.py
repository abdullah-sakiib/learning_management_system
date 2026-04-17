from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_modulecompletion"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="teacher_id",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="profile",
            name="university",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="profile",
            name="designation",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]

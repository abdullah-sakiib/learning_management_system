from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_course_media_modules_resources"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="assignment",
            name="attachment",
            field=models.FileField(blank=True, null=True, upload_to="assignment_attachments/%Y/%m/%d/"),
        ),
        migrations.AddField(
            model_name="assignment",
            name="publish_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

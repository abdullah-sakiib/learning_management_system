from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_profile_contact_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="intro_video",
            field=models.FileField(blank=True, null=True, upload_to="course_intro_videos/"),
        ),
        migrations.AddField(
            model_name="course",
            name="thumbnail",
            field=models.ImageField(blank=True, null=True, upload_to="course_thumbnails/"),
        ),
        migrations.CreateModel(
            name="CourseModule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("overview", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=1)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "course",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="modules", to="core.course"),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ModuleResource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                (
                    "resource_type",
                    models.CharField(
                        choices=[("video", "Video"), ("file", "File"), ("link", "External Link")],
                        default="file",
                        max_length=20,
                    ),
                ),
                ("video_file", models.FileField(blank=True, null=True, upload_to="module_videos/%Y/%m/%d/")),
                ("file", models.FileField(blank=True, null=True, upload_to="module_files/%Y/%m/%d/")),
                ("external_url", models.URLField(blank=True)),
                ("duration_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("order", models.PositiveIntegerField(default=1)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "module",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resources", to="core.coursemodule"),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
    ]

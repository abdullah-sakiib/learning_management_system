from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_assignment_publish_attachment_archive"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModuleCompletion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("completed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "enrollment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="module_completions",
                        to="core.enrollment",
                    ),
                ),
                (
                    "module",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="completions",
                        to="core.coursemodule",
                    ),
                ),
            ],
            options={
                "ordering": ["-completed_at"],
                "unique_together": {("enrollment", "module")},
            },
        ),
    ]

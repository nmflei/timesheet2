from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("timesheets", "0003_userlanguagepreference"),
    ]

    operations = [
        migrations.DeleteModel(
            name="UserLanguagePreference",
        ),
    ]

from django.db import migrations

from audit import append_only


class Migration(migrations.Migration):
    """PostgreSQL only: reject UPDATE and DELETE on the audit, seal, access-log and verification-evidence tables."""

    dependencies = [
        ('audit', '0001_initial'),
        ('portal', '0005_record_fields'),
        ('access', '0001_initial'),
        ('verification', '0002_alter_verificationevidence_method_and_more'),
    ]

    operations = [
        migrations.RunPython(append_only.install, append_only.remove),
    ]

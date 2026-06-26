from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ai", "0002_chat_history")]
    operations = [
        migrations.RemoveConstraint(model_name="chatconversation", name="unique_user_chat_scope"),
        migrations.AddField(model_name="chatconversation", name="archived_at", field=models.DateTimeField(blank=True, null=True)),
    ]

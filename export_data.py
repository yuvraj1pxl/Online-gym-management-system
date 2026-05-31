import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gym.settings')
django.setup()

from django.core.serializers import serialize
from django.apps import apps

all_data = []

excluded = ['contenttypes', 'auth.permission']

for model in apps.get_models():
    label = f"{model._meta.app_label}.{model.__name__}".lower()
    if any(ex in label for ex in excluded):
        continue
    try:
        data = json.loads(serialize('json', model.objects.all()))
        all_data.extend(data)
        print(f"Exported {len(data)} records from {label}")
    except Exception as e:
        print(f"Skipped {label}: {e}")

with open('datadump.json', 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print("Done! datadump.json created.")
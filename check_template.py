import sys
sys.path.insert(0, '.')

from db.db import get_db
from db.models.templates import TemplateModel

db = next(get_db())

# Check if intent_v1 exists
template = db.query(TemplateModel).filter(TemplateModel.template_key == 'intent_v1').first()

if not template:
    print("❌ intent_v1 NOT FOUND")
    print("\nAvailable templates:")
    all_templates = db.query(TemplateModel.template_key, TemplateModel.name).all()
    for t in all_templates:
        print(f"  - {t.template_key}: {t.name}")
else:
    print(f"✅ Found: {template.template_key}")
    print(f"\nSections JSONB:")
    print(template.sections)

db.close()
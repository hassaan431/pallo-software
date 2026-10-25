# Unified Authentication, Session Scoping and Company Context

Type: task
Status: open
Blocked by: none (03 resolved)

## Question

How do we adapt the Flask-Login `User` model, session deserialization, and `@app.context_processor` in [app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py) so that entering credentials on the unified `/login` page immediately resolves the user to their `company_id`, enforces soft-deactivation checks (`company.is_active == 1`), and injects `current_company` into all Jinja2 templates?

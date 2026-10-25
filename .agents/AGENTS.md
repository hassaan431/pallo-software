# Deployment Workflow Rules

Whenever making code changes to this project, you MUST follow this workflow:

1. **Test Locally First**: After making code changes, run the application locally to test it. Start the application using `python3 launch.py` as a background command so the user can test the app in their local browser.
2. **Push to GitHub (Pallo Repository ONLY)**: This project is strictly Pallo SaaS and must ONLY be pushed to `origin` (`https://github.com/hassaan431/pallo-software.git`). NEVER push to or reference `ak-distributors-app`. Once testing is complete and the user has explicitly verified the changes and told you to commit, then you can commit all changes and push them to the GitHub repository (`git add .`, `git commit -m "..."`, `git push origin main`). DO NOT auto-commit without asking first.
3. **Deploy to Web**: Inform the user to trigger deployment on their hosting console (e.g. Render) to apply the changes to the live version.

# Restart Rule

Whenever making any code changes to the backend or HTML templates, you MUST restart the local server automatically so the user can immediately see the changes, without the user having to explicitly ask for a restart. You can restart using `lsof -t -i :5000 | xargs kill -9 && python3 launch.py`.

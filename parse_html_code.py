from bs4 import BeautifulSoup
import json

with open('/Users/hassaanjazz/.gemini/antigravity-ide/brain/32313f4e-5957-4569-b428-25fb5efec103/.system_generated/steps/2297/content.md', 'r') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

codes = soup.find_all('code')
for i, c in enumerate(codes):
    text = c.get_text()
    if 'import' in text and 'motion' in text and 'svg' in text.lower():
        print(f"--- Code block {i} ---")
        print(text)


from bs4 import BeautifulSoup
import re

with open('/Users/hassaanjazz/.gemini/antigravity-ide/brain/32313f4e-5957-4569-b428-25fb5efec103/.system_generated/steps/2297/content.md', 'r') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Find all code blocks
codes = soup.find_all('code')
for c in codes:
    text = c.get_text()
    if 'npx' in text or 'npm' in text or 'import' in text:
        print(text[:200] + '...')

print("---")
# Or look for specific script tags that might have the code
for script in soup.find_all('script'):
    if script.string and 'skiper19' in script.string:
        # try to extract the registry url or code
        matches = re.findall(r'https?://[^\s"]+', script.string)
        for m in matches:
            if 'registry' in m or 'json' in m:
                print("Found registry url:", m)

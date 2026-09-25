from xhtml2pdf import pisa
import PyPDF2

def test_html(html_snippet):
    html = f"""
    <!DOCTYPE html>
    <html>
    <body>
        <table style="width: 100%;">
            {html_snippet}
            <tbody>
                <tr><td style="height: 500pt;">Row 1</td></tr>
                <tr><td style="height: 500pt;">Row 2</td></tr>
                <tr><td style="height: 500pt;">Row 3</td></tr>
            </tbody>
        </table>
    </body>
    </html>
    """
    with open("test2.pdf", "wb") as f:
        pisa.CreatePDF(html, dest=f)
    
    with open("test2.pdf", "rb") as f:
        pdf = PyPDF2.PdfReader(f)
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text.count("HEADER REPEAT")

print("Test 1 (repeat=1 on thead):", test_html('<thead repeat="1"><tr><th style="font-size: 20pt;">HEADER REPEAT</th></tr></thead>'))
print("Test 2 (repeat=repeat on thead):", test_html('<thead repeat="repeat"><tr><th style="font-size: 20pt;">HEADER REPEAT</th></tr></thead>'))
print("Test 3 (display: table-header-group):", test_html('<thead style="display: table-header-group"><tr><th style="font-size: 20pt;">HEADER REPEAT</th></tr></thead>'))

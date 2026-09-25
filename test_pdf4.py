from xhtml2pdf import pisa
import PyPDF2

def test_html(html_snippet):
    html = f"""
    <!DOCTYPE html>
    <html>
    <body>
        {html_snippet}
            <thead>
                <tr><th style="font-size: 20pt;">HEADER REPEAT</th></tr>
            </thead>
            <tbody>
                <tr><td style="height: 500pt;">Row 1</td></tr>
                <tr><td style="height: 500pt;">Row 2</td></tr>
                <tr><td style="height: 500pt;">Row 3</td></tr>
            </tbody>
        </table>
    </body>
    </html>
    """
    with open("test4.pdf", "wb") as f:
        pisa.CreatePDF(html, dest=f)
    
    with open("test4.pdf", "rb") as f:
        pdf = PyPDF2.PdfReader(f)
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text.count("HEADER REPEAT")

print("Test 1 (table repeat=1):", test_html('<table style="width: 100%;" repeat="1">'))

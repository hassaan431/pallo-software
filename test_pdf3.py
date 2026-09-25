from xhtml2pdf import pisa
import PyPDF2

html = """
<!DOCTYPE html>
<html>
<head>
<style>
    @page {
        size: A4; margin: 1cm;
    }
    @page brand1 {
        size: A4; margin: 1cm; margin-top: 3cm;
        @frame header1 {
            -pdf-frame-content: header_brand1;
            left: 1cm; right: 1cm; top: 1cm; height: 2cm;
        }
    }
</style>
</head>
<body>
    <h1>First Page</h1>
    <pdf:nexttemplate name="brand1" />
    <pdf:nextpage />
    <div id="header_brand1">HEADER REPEAT</div>
    <div style="height: 500pt;">Row 1</div>
    <div style="height: 500pt;">Row 2</div>
    <div style="height: 500pt;">Row 3</div>
</body>
</html>
"""
with open("test3.pdf", "wb") as f:
    pisa.CreatePDF(html, dest=f)

with open("test3.pdf", "rb") as f:
    pdf = PyPDF2.PdfReader(f)
    text = ""
    for page in pdf.pages:
        text += page.extract_text()
print("Header occurrences:", text.count("HEADER REPEAT"))

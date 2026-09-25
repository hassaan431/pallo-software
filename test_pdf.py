from xhtml2pdf import pisa

html = """
<!DOCTYPE html>
<html>
<body>
    <table style="width: 100%;">
        <thead>
            <tr repeat="1">
                <th style="background-color: #eee; font-size: 20pt; padding: 10pt;">HEADER REPEAT</th>
            </tr>
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
with open("test.pdf", "wb") as f:
    pisa.CreatePDF(html, dest=f)

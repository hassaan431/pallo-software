import io
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from database import get_connection


_DARK_NAVY = colors.HexColor("#1a2332")
_LIGHT_GREY = colors.HexColor("#f4f6f9")
_VERY_LIGHT_GREY = colors.HexColor("#f8f8f8")
_TEXT_GREY = colors.HexColor("#6b7280")

_LOGO_MAX_SIZE = 70  # points (approx to requested 70x70px)
_LEFT_MARGIN_FALLBACK = 36

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ak_logo_path = os.path.join(
    BASE_DIR, "static", "logos", "AK Distributors Logo.jpeg"
)
zain_logo_path = os.path.join(
    BASE_DIR, "static", "logos", "Zain Foods Logo.jpeg"
)


def _format_date(val):
    if not val:
        return ""
    s = str(val).strip()
    # Expect YYYY-MM-DD from HTML date input
    try:
        d = datetime.fromisoformat(s).date()
        return d.strftime("%d %b %Y")
    except ValueError:
        # Try common variants
        for fmt in ("%Y-%m-%d", "%d %b %Y", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                d = datetime.strptime(s, fmt).date()
                return d.strftime("%d %b %Y")
            except ValueError:
                continue
    return s


def _wrap_text_lines(cnv, text, font_name, font_size, max_width):
    """
    Wraps text into lines that fit within max_width using simple word-wrapping.
    Preserves newlines by splitting into paragraphs.
    """
    if text is None:
        return [""]
    raw = str(text).replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = raw.split("\n")
    lines = []
    for para in paragraphs:
        words = para.split(" ")
        current = ""
        for w in words:
            candidate = w if not current else current + " " + w
            width = pdfmetrics.stringWidth(candidate, font_name, font_size)
            if width <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = w
        lines.append(current)
    # Avoid trailing empties for nicer row heights
    if lines and lines[-1] == "":
        lines = lines[:-1] if len(lines) > 1 else lines
    return lines if lines else [""]


def _draw_centered_text(cnv, x_center, y, text, font_name, font_size, fill_color=colors.black):
    cnv.setFillColor(fill_color)
    cnv.setFont(font_name, font_size)
    width = pdfmetrics.stringWidth(text, font_name, font_size)
    cnv.drawString(x_center - width / 2.0, y, text)


def _draw_logo_placeholder(cnv, x, y, w, h, label):
    cnv.saveState()
    cnv.setFillColor(_VERY_LIGHT_GREY)
    cnv.setStrokeColor(colors.HexColor("#d1d5db"))
    cnv.setLineWidth(1)
    cnv.roundRect(x, y, w, h, 10, stroke=1, fill=1)
    _draw_centered_text(cnv, x + w / 2.0, y + h / 2.0 - 7, label, "Helvetica-Bold", 16, _DARK_NAVY)
    cnv.restoreState()


def _draw_logo(cnv, logo_path: str, x: float, y: float, max_size: float):
    """
    Draws a logo image at (x, y) scaled to max_size x max_size.
    Returns drawn width (points) when successful, else None.
    """
    if not os.path.exists(logo_path):
        return None
    try:
        img = ImageReader(logo_path)
        img_w, img_h = img.getSize()
        if img_w <= 0 or img_h <= 0:
            return None
        scale = min(max_size / float(img_w), max_size / float(img_h))
        draw_w = img_w * scale
        draw_h = img_h * scale
        cnv.drawImage(
            img,
            x,
            y,
            width=draw_w,
            height=draw_h,
            preserveAspectRatio=True,
            mask="auto",
        )
        return draw_w
    except Exception:
        return None


def generate_invoice_pdf(sale_id: int) -> bytes:
    """
    Generates a PDF invoice for the given sale_id.
    Returns raw PDF bytes.
    """
    conn = get_connection()
    try:
        sale = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                s.due_date,
                s.terms,
                s.subtotal,
                s.discount_amount,
                s.grand_total,
                s.customer_id
            FROM sales s
            WHERE s.id = ?
            """,
            (sale_id,),
        ).fetchone()
        if sale is None:
            raise ValueError(f"Sale not found: {sale_id}")

        customer = conn.execute(
            """
            SELECT
                id,
                name,
                bill_address,
                ship_address,
                phone
            FROM customers
            WHERE id = ?
            """,
            (sale["customer_id"],),
        ).fetchone()
        if customer is None:
            raise ValueError(f"Customer not found for sale: {sale_id}")

        sale_items = conn.execute(
            """
            SELECT
                si.id AS sale_item_id,
                si.product_id,
                si.description,
                si.qty,
                si.rate,
                si.amount,
                p.name AS product_name,
                p.brand AS product_brand
            FROM sale_items si
            LEFT JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
            ORDER BY si.id ASC
            """,
            (sale_id,),
        ).fetchall()
    finally:
        conn.close()

    # Page setup
    page_width, page_height = letter  # (612, 792)
    margin = 0.5 * inch  # 36pt
    usable_width = page_width - (2 * margin)

    # Layout metrics
    header_height = 88
    meta_height = 74  # Increased from 58 for 8pt padding top/bottom
    bill_height = 112
    spacer_after_header = 12  # Increased from 8
    spacer_after_meta = 10  # Increased from 8
    table_header_height = 22

    totals_block_height = 90
    footer_height = 28

    # Column widths
    col_no = 0.3 * inch
    col_item = 3.5 * inch
    col_qty = 0.8 * inch
    col_rate = 1.2 * inch
    col_amt = 1.2 * inch
    col_total = col_no + col_item + col_qty + col_rate + col_amt
    # If column sum drift due to float, normalize by scaling to usable_width
    scale = usable_width / col_total
    col_no *= scale
    col_item *= scale
    col_qty *= scale
    col_rate *= scale
    col_amt *= scale

    x0 = margin
    x_no_right = x0 + col_no
    x_item_right = x_no_right + col_item
    x_qty_right = x_item_right + col_qty
    x_rate_right = x_qty_right + col_rate
    x_amt_right = x_rate_right + col_amt

    row_padding_y = 8  # Increased from 6 for 4pt padding
    row_leading_item = 12
    row_leading_brand = 10
    min_row_height = 20  # Minimum row height in points

    # Prepare rows with wrapping & computed heights
    dark_text = colors.black
    brand_font = "Helvetica-Oblique"
    item_font = "Helvetica"
    brand_font_size = 8
    item_font_size = 10
    max_item_width = col_item - 10  # left+right padding for cell

    row_models = []
    for i, it in enumerate(sale_items):
        description = it["description"] or ""
        product_name = (it["product_name"] or "").strip()
        product_brand = (it["product_brand"] or "").strip()

        # Use sale_item.description to infer item+brand if product brand isn't available.
        item_line = description
        desc_brand = None
        if " - " in description:
            parts = [p.strip() for p in description.split(" - ", 1)]
            if len(parts) == 2:
                item_line = parts[0] or description
                desc_brand = parts[1] or None

        brand_line = product_brand or desc_brand
        brand_line = brand_line.strip() if brand_line else ""

        item_lines = _wrap_text_lines(
            None, item_line, item_font, item_font_size, max_item_width
        )
        brand_lines = []
        if brand_line:
            brand_lines = _wrap_text_lines(
                None, brand_line, brand_font, brand_font_size, max_item_width
            )

        line_count = len(item_lines) + len(brand_lines)
        leading_total = len(item_lines) * row_leading_item + len(brand_lines) * row_leading_brand
        row_height = leading_total + (2 * row_padding_y)

        row_models.append(
            {
                "idx": i,
                "sale_item": it,
                "item_lines": item_lines,
                "brand_lines": brand_lines,
                "row_height": row_height,
            }
        )

    # Compute pagination
    table_start_y = page_height - margin - header_height - spacer_after_header - meta_height - spacer_after_meta - bill_height - table_header_height
    table_header_y = table_start_y + 0  # not used directly

    # Actually draw: start below table header
    content_start_y = page_height - margin - header_height - spacer_after_header - meta_height - spacer_after_meta - bill_height - table_header_height
    # content_start_y is y after drawing table header? It depends on bottom-up.
    # We'll place table header at y_header_bottom and then set content_start_y = y_header_bottom - 0.
    # For simplicity, compute y positions dynamically per page during drawing.

    def draw_header_and_table_header(cnv, inv_data, cust_data, y_top):
        """
        Draws header, meta box, bill/ship box, and the table column header.
        Returns y_cursor at the top of the first items row (y value to start drawing next).
        """
        invoice_x_right = x0 + usable_width

        # Header: logos + company info + INVOICE word
        max_size = _LOGO_MAX_SIZE
        ak_x = 36  # points from left (as requested)
        logos_y = y_top - max_size + 6

        # Draw AK logo, fallback to placeholder (if missing).
        ak_draw_w = _draw_logo(cnv, ak_logo_path, ak_x, logos_y, max_size)
        if ak_draw_w is None:
            _draw_logo_placeholder(cnv, ak_x, logos_y, max_size, max_size, "AK")
            ak_draw_w = float(max_size)

        # Draw Zain logo 10pt to the right of AK logo.
        zain_x = ak_x + ak_draw_w + 10
        zain_draw_w = _draw_logo(cnv, zain_logo_path, zain_x, logos_y, max_size)
        if zain_draw_w is None:
            _draw_logo_placeholder(cnv, zain_x, logos_y, max_size, max_size, "ZAIN")
            zain_draw_w = float(max_size)

        company_x = zain_x + max_size + 18
        company_y = y_top - 18

        cnv.setFont("Helvetica-Bold", 13)
        cnv.setFillColor(_DARK_NAVY)
        cnv.drawString(company_x, company_y, "AK DISTRIBUTORS LLC")
        cnv.setFont("Helvetica", 10)
        cnv.setFillColor(_TEXT_GREY)
        cnv.drawString(company_x, company_y - 15, "Sacramento California 95838")
        cnv.drawString(company_x, company_y - 30, "U.S.A")
        cnv.drawString(company_x, company_y - 45, "9163545678")
        cnv.drawString(company_x, company_y - 60, "akdistributorsusa@gmail.com")

        # INVOICE label far right
        cnv.setFont("Helvetica-Bold", 28)
        cnv.setFillColor(_DARK_NAVY)
        cnv.drawRightString(invoice_x_right, y_top - 34, "INVOICE")

        # Horizontal line below header
        cnv.setStrokeColor(colors.HexColor("#d1d5db"))
        cnv.setLineWidth(1)
        cnv.line(x0, y_top - header_height + 8, x0 + usable_width, y_top - header_height + 8)

        # Meta info box
        meta_box_top = y_top - header_height + 8 - 10
        meta_box_bottom = meta_box_top - meta_height
        cnv.setStrokeColor(colors.HexColor("#d1d5db"))
        cnv.setFillColor(colors.white)
        cnv.roundRect(x0, meta_box_bottom, usable_width, meta_height, 6, stroke=1, fill=1)

        meta_rows = [
            ("Invoice #", inv_data["invoice_number"]),
            ("Invoice Date", _format_date(inv_data["invoice_date"])),
            ("Terms", inv_data["terms"] or ""),
            ("Due Date", _format_date(inv_data["due_date"] or inv_data["invoice_date"])),
        ]

        label_x = x0 + 18
        value_x = x0 + 135
        row_step = meta_height / 4.0
        cnv.setFont("Helvetica", 10)
        for idx, (lab, val) in enumerate(meta_rows):
            y_text = meta_box_top - row_step * (idx + 0.5) + 1
            cnv.setFillColor(_TEXT_GREY)
            cnv.setFont("Helvetica", 10)
            cnv.drawString(label_x, y_text, lab)
            cnv.setFillColor(colors.black)
            cnv.setFont("Helvetica-Bold", 10)
            cnv.drawString(value_x, y_text, str(val or ""))

        # Bill To / Ship To box
        bill_box_top = meta_box_bottom - spacer_after_meta
        bill_box_bottom = bill_box_top - bill_height
        cnv.setFillColor(_LIGHT_GREY)
        cnv.setStrokeColor(colors.HexColor("#d1d5db"))
        cnv.roundRect(x0, bill_box_bottom, usable_width, bill_height, 6, stroke=1, fill=1)

        half_w = usable_width / 2.0
        left_x = x0 + 16
        right_x = x0 + half_w + 16
        inner_w = half_w - 32

        bill_label_y = bill_box_top - 18
        ship_label_y = bill_label_y
        cnv.setFillColor(_TEXT_GREY)
        cnv.setFont("Helvetica", 8.5)
        cnv.drawString(left_x, bill_label_y, "Bill To")
        cnv.drawString(right_x, ship_label_y, "Ship To")

        # Address handling
        bill_name = cust_data.get("name") or ""
        bill_address = (cust_data.get("bill_address") or "").strip()
        bill_phone = (cust_data.get("phone") or "").strip()
        ship_address = (cust_data.get("ship_address") or "").strip()

        # If ship is empty or same, copy billing
        if not ship_address:
            ship_address = bill_address
        else:
            if ship_address.strip() == bill_address.strip():
                ship_address = bill_address

        # Draw billing column
        cnv.setFillColor(_DARK_NAVY)
        cnv.setFont("Helvetica-Bold", 12)
        cnv.drawString(left_x, bill_box_top - 40, bill_name)
        cnv.setFillColor(colors.black)
        cnv.setFont("Helvetica", 10)
        # Wrap address text
        addr_y = bill_box_top - 55
        bill_lines = _wrap_text_lines(cnv, bill_address, "Helvetica", 10, inner_w)
        for ln in bill_lines:
            cnv.drawString(left_x, addr_y, ln)
            addr_y -= 13
        
        # Add phone number if available
        if bill_phone:
            cnv.setFillColor(colors.black)
            cnv.setFont("Helvetica", 10)  # 10pt font as requested
            cnv.drawString(left_x, addr_y, bill_phone)
            addr_y -= 13

        # Draw shipping column
        cnv.setFillColor(_DARK_NAVY)
        cnv.setFont("Helvetica-Bold", 10)
        cnv.drawString(right_x, bill_box_top - 40, "")  # intentionally blank (label only in spec)
        cnv.setFillColor(colors.black)
        cnv.setFont("Helvetica", 10)
        addr_y2 = bill_box_top - 55
        ship_lines = _wrap_text_lines(cnv, ship_address, "Helvetica", 10, inner_w)
        for ln in ship_lines:
            cnv.drawString(right_x, addr_y2, ln)
            addr_y2 -= 13

        # Dividing line between columns
        cnv.setStrokeColor(colors.HexColor("#d1d5db"))
        cnv.line(x0 + half_w, bill_box_bottom + 8, x0 + half_w, bill_box_top - 8)

        # Table header row
        y_header_bottom = bill_box_bottom - table_header_height - 18
        cnv.setFillColor(_DARK_NAVY)
        cnv.setStrokeColor(_DARK_NAVY)
        cnv.rect(x0, y_header_bottom, usable_width, table_header_height, stroke=0, fill=1)

        cnv.setFillColor(colors.white)
        cnv.setFont("Helvetica-Bold", 9)
        header_y_text = y_header_bottom + 6

        # Labels
        cnv.drawString(x0 + 6, header_y_text, "#")
        cnv.drawString(x_no_right + 6, header_y_text, "ITEM & DESCRIPTION")
        cnv.drawString(x_item_right + 10, header_y_text, "QTY")
        cnv.drawString(x_qty_right + 6, header_y_text, "RATE")
        cnv.drawString(x_rate_right + 10, header_y_text, "AMOUNT")

        cnv.setFillColor(colors.black)
        cnv.setLineWidth(1)

        # Cursor where the first row begins
        return y_header_bottom

    # Prepare invoice data for drawing
    inv_data = {
        "invoice_number": sale["invoice_number"],
        "invoice_date": sale["invoice_date"],
        "due_date": sale["due_date"],
        "terms": sale["terms"] or "",
        "subtotal": float(sale["subtotal"] or 0),
        "discount_amount": float(sale["discount_amount"] or 0),
        "grand_total": float(sale["grand_total"] or 0),
    }

    cust_data = {
        "name": customer["name"],
        "bill_address": customer["bill_address"] or "",
        "ship_address": customer["ship_address"] or "",
    }

    buf = io.BytesIO()
    cnv = canvas.Canvas(buf, pagesize=letter)
    cnv.setTitle(inv_data["invoice_number"])

    # Pagination decision
    idx = 0
    row_alternator = 0
    sale_rows_total = len(row_models)

    # Limits
    y_last_items_limit = margin + footer_height + 26 + totals_block_height  # distance from bottom
    # Use bottom-up coordinates: y cannot go below this threshold while drawing table rows
    table_bottom_floor_regular = margin + 40
    table_bottom_floor_last = margin + totals_block_height + footer_height + 26

    while idx < sale_rows_total:
        # Determine if this page is last by checking remaining height vs available height
        remaining = sale_rows_total - idx
        remaining_height = sum(row_models[j]["row_height"] for j in range(idx, sale_rows_total))

        # Draw header and get y cursor for table header bottom
        y_top = page_height - margin
        y_cursor = draw_header_and_table_header(cnv, inv_data, cust_data, y_top=y_top)
        # y_cursor is table header bottom; rows go downward, so starting row bottom is below header
        y_cursor -= 2  # small spacing

        table_bottom_floor = table_bottom_floor_last if remaining_height <= (y_cursor - table_bottom_floor_last) else table_bottom_floor_regular
        page_is_last = table_bottom_floor == table_bottom_floor_last

        # Draw item rows until floor reached
        while idx < sale_rows_total:
            row = row_models[idx]
            rh = row["row_height"]

            if y_cursor - rh < table_bottom_floor:
                break

            row_bottom = y_cursor - rh

            # Row background
            cnv.setFillColor(_VERY_LIGHT_GREY if row_alternator % 2 == 0 else colors.white)
            cnv.setStrokeColor(colors.HexColor("#e5e7eb"))
            cnv.rect(x0, row_bottom, usable_width, rh, stroke=0, fill=1)

            # Divider line subtle
            # Item number
            qty = row["sale_item"]["qty"]
            rate = row["sale_item"]["rate"]
            amount = row["sale_item"]["amount"]

            # Text positions
            tx = x0 + 6
            ty = row_bottom + rh - row_padding_y - row_leading_item
            cnv.setFillColor(colors.black)
            cnv.setFont("Helvetica", 10)
            cnv.drawString(tx, ty, str(idx + 1))

            # Item text: draw item name lines and brand lines
            item_cell_x = x_no_right + 6
            current_y = row_bottom + rh - row_padding_y - row_leading_item
            for line in row["item_lines"]:
                cnv.setFillColor(colors.black)
                cnv.setFont("Helvetica", 10)
                cnv.drawString(item_cell_x, current_y, line)
                current_y -= row_leading_item

            for bline in row["brand_lines"]:
                cnv.setFillColor(_TEXT_GREY)
                cnv.setFont(brand_font, brand_font_size)
                cnv.drawString(item_cell_x, current_y, bline)
                current_y -= row_leading_brand

            # Qty/Rate/Amount right aligned
            cnv.setFillColor(colors.black)
            cnv.setFont("Helvetica", 10)
            qty_str = f"{float(qty):g}" if qty is not None else "0"
            # Align right with padding
            qty_x_right = x_qty_right - 6
            rate_x_right = x_rate_right - 6
            amt_x_right = x_amt_right - 6
            cnv.drawRightString(qty_x_right, row_bottom + row_padding_y + 2, qty_str)
            cnv.drawRightString(rate_x_right, row_bottom + row_padding_y + 2, f"${float(rate or 0):.2f}")
            cnv.drawRightString(amt_x_right, row_bottom + row_padding_y + 2, f"${float(amount or 0):.2f}")

            # Move cursor down
            y_cursor = row_bottom
            idx += 1
            row_alternator += 1

        # Totals + footer on last page only
        if page_is_last:
            # Draw totals near bottom-right
            totals_right_x = x0 + usable_width
            totals_x = totals_right_x - 260
            totals_y_top = margin + table_bottom_floor_last - margin  # not reliable
            # We'll anchor by absolute bottom positions
            totals_bottom = margin + footer_height + 18
            totals_top = totals_bottom + totals_block_height

            # Line above totals
            cnv.setStrokeColor(_DARK_NAVY)
            cnv.setLineWidth(1)
            cnv.line(totals_x, totals_top - 10, totals_right_x, totals_top - 10)

            cnv.setFont("Helvetica", 10)
            cnv.setFillColor(colors.black)

            subtotal = inv_data["subtotal"]
            discount_amount = inv_data["discount_amount"]
            grand_total = inv_data["grand_total"]

            # Right-aligned totals
            cnv.drawRightString(totals_right_x, totals_top - 28, f"Subtotal:       ${subtotal:.2f}")
            if discount_amount > 0:
                cnv.drawRightString(totals_right_x, totals_top - 44, f"Discount:      -${discount_amount:.2f}")

            # Add separator line
            cnv.setFillColor(colors.black)
            cnv.setStrokeColor(colors.black)
            cnv.setLineWidth(1)
            line_y = totals_top - 54
            cnv.line(totals_x, line_y, totals_right_x, line_y)

            # Grand total block with navy background and white text
            cnv.setFillColor(_DARK_NAVY)
            cnv.setStrokeColor(_DARK_NAVY)
            grand_y = totals_bottom + 10
            grand_h = 32
            cnv.rect(totals_x, grand_y, totals_right_x - totals_x, grand_h, stroke=0, fill=1)
            cnv.setFillColor(colors.white)
            cnv.setFont("Helvetica-Bold", 12)  # 12pt font as requested
            cnv.drawRightString(totals_right_x - 6, grand_y + 10, f"GRAND TOTAL:    ${grand_total:.2f}")

            # Footer
            cnv.setFillColor(_TEXT_GREY)
            cnv.setFont("Helvetica", 9)
            cnv.drawString(x0, margin + 10, "Thank you for your business!")
            cnv.setFont("Helvetica", 7)
            cnv.drawString(x0, margin + 2, "Generated by AK Distributors App")

        cnv.showPage()

    cnv.save()
    return buf.getvalue()


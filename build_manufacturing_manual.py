from pathlib import Path
import re
import zipfile
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.section import WD_SECTION


ROOT = Path(r"C:\Users\SONAL\OneDrive\Documents\Legacy")
ASSETS = ROOT / "manual_assets"
OUTPUT = ROOT / "Legacy_Odoo17_Manufacturing_User_Manual.docx"

NAVY = "0B2545"
BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
LIGHT_BLUE = "E8EEF5"
PALE_BLUE = "F4F7FA"
GOLD = "B4862C"
GRAY = "5D6670"
LIGHT_GRAY = "F2F4F7"
WHITE = "FFFFFF"
RED = "9B1C1C"
GREEN = "2E6B4F"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths_dxa, indent_dxa=120):
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths_dxa)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(widths_dxa[idx]))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_run_font(run, name="Calibri", size=None, color=None, bold=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def add_field(run, instruction):
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr)
    run._r.append(fld_char2)


def add_alt_text(inline_shape, title, description):
    doc_pr = inline_shape._inline.docPr
    doc_pr.set("title", title)
    doc_pr.set("descr", description)


def style_document(doc):
    doc.settings.odd_and_even_pages_header_footer = False
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)
    section.different_first_page_header_footer = False

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    for name, size, color, before, after in (
        ("Heading 1", 16, BLUE, 18, 10),
        ("Heading 2", 13, BLUE, 14, 7),
        ("Heading 3", 12, DARK_BLUE, 10, 5),
    ):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        st._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor.from_string(color)
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.keep_with_next = True

    for name in ("List Bullet", "List Number"):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(11)
        st.paragraph_format.left_indent = Inches(0.375)
        st.paragraph_format.first_line_indent = Inches(-0.188)
        st.paragraph_format.space_after = Pt(4)
        st.paragraph_format.line_spacing = 1.25

    caption = doc.styles["Caption"]
    caption.font.name = "Calibri"
    caption.font.size = Pt(9)
    caption.font.italic = True
    caption.font.color.rgb = RGBColor.from_string(GRAY)
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(4)
    caption.paragraph_format.space_after = Pt(10)
    caption.paragraph_format.keep_with_next = False

    if "Callout" not in doc.styles:
        callout = doc.styles.add_style("Callout", WD_STYLE_TYPE.PARAGRAPH)
    else:
        callout = doc.styles["Callout"]
    callout.font.name = "Calibri"
    callout.font.size = Pt(10.5)
    callout.font.color.rgb = RGBColor.from_string(NAVY)
    callout.paragraph_format.left_indent = Inches(0.18)
    callout.paragraph_format.right_indent = Inches(0.12)
    callout.paragraph_format.space_before = Pt(7)
    callout.paragraph_format.space_after = Pt(9)
    callout.paragraph_format.line_spacing = 1.2

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hr = hp.add_run("LEGACY MANUFACTURERS LIMITED  |  ODOO 17 MANUFACTURING")
    set_run_font(hr, size=8.5, color=GRAY, bold=True)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fr = fp.add_run("Manufacturing User Manual  |  Page ")
    set_run_font(fr, size=8.5, color=GRAY)
    field_run = fp.add_run()
    set_run_font(field_run, size=8.5, color=GRAY)
    add_field(field_run, "PAGE")

    even_header = section.even_page_header
    ehp = even_header.paragraphs[0]
    ehp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    ehr = ehp.add_run("LEGACY MANUFACTURERS LIMITED  |  ODOO 17 MANUFACTURING")
    set_run_font(ehr, size=8.5, color=GRAY, bold=True)

    even_footer = section.even_page_footer
    efp = even_footer.paragraphs[0]
    efp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    efr = efp.add_run("Manufacturing User Manual  |  Page ")
    set_run_font(efr, size=8.5, color=GRAY)
    even_field_run = efp.add_run()
    set_run_font(even_field_run, size=8.5, color=GRAY)
    add_field(even_field_run, "PAGE")


def add_callout(doc, label, text, color=BLUE, fill=PALE_BLUE):
    p = doc.add_paragraph(style="Callout")
    p_pr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    p_pr.append(shd)
    borders = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:space"), "6")
    left.set(qn("w:color"), color)
    borders.append(left)
    p_pr.append(borders)
    r1 = p.add_run(label + "  ")
    set_run_font(r1, size=10.5, color=color, bold=True)
    r2 = p.add_run(text)
    set_run_font(r2, size=10.5, color=NAVY)
    return p


def add_step(doc, number, title, body):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.keep_with_next = False
    badge = p.add_run(f"STEP {number}  ")
    # Keep the step marker as colored text. Word's run-level shading can
    # intermittently drop leading glyphs when the document is repaginated.
    set_run_font(badge, size=10, color=BLUE, bold=True)
    title_run = p.add_run(title)
    set_run_font(title_run, size=12, color=NAVY, bold=True)
    line_break = p.add_run()
    line_break.add_break()
    body_run = p.add_run(body)
    set_run_font(body_run, size=11, color="000000")
    return p


def add_bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix and text.startswith(bold_prefix):
        r1 = p.add_run(bold_prefix)
        set_run_font(r1, bold=True, color=NAVY)
        p.add_run(text[len(bold_prefix):])
    else:
        p.add_run(text)
    return p


def add_number(doc, text):
    return doc.add_paragraph(text, style="List Number")


def add_data_table(doc, headers, rows, widths_dxa):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for i, text in enumerate(headers):
        set_cell_shading(hdr.cells[i], LIGHT_BLUE)
        p = hdr.cells[i].paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        set_run_font(r, size=9.5, color=NAVY, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for i, text in enumerate(row):
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(str(text))
            set_run_font(r, size=9.5, color=NAVY)
    set_table_geometry(table, widths_dxa)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_checklist_table(doc, items):
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    for item in items:
        cells = table.add_row().cells
        set_cell_shading(cells[0], LIGHT_GRAY)
        marker = cells[0].paragraphs[0]
        marker.alignment = WD_ALIGN_PARAGRAPH.CENTER
        marker.paragraph_format.space_after = Pt(0)
        mr = marker.add_run("[ ]")
        set_run_font(mr, size=10, color=BLUE, bold=True)
        text_p = cells[1].paragraphs[0]
        text_p.paragraph_format.space_after = Pt(0)
        tr = text_p.add_run(item)
        set_run_font(tr, size=10, color=NAVY)
    set_table_geometry(table, [650, 8710])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_screenshot(doc, filename, caption, alt):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    shape = p.add_run().add_picture(str(ASSETS / filename), width=Inches(5.8))
    add_alt_text(shape, caption, alt)
    cp = doc.add_paragraph(caption, style="Caption")
    return cp


def add_page_title(doc, title, subtitle=None):
    p = doc.add_paragraph()
    if getattr(doc, "_manual_break_pending", False):
        p.paragraph_format.page_break_before = True
        doc._manual_break_pending = False
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(title)
    set_run_font(r, size=20, color=NAVY, bold=True)
    if subtitle:
        s = doc.add_paragraph()
        s.paragraph_format.space_after = Pt(10)
        rr = s.add_run()
        rr.text = subtitle
        set_run_font(rr, size=11, color=GRAY, italic=True)


def page_break(doc):
    doc._manual_break_pending = True


def force_shared_odd_even_headers(path):
    """Remove unstable running furniture; the manual uses body navigation instead."""
    temp_path = path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(path, "r") as src, zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as dst:
        document_xml = src.read("word/document.xml").decode("utf-8")
        settings_xml = src.read("word/settings.xml").decode("utf-8")
        document_xml = re.sub(r'<w:headerReference w:type="[^"]+" r:id="[^"]+"/>', "", document_xml)
        document_xml = re.sub(r'<w:footerReference w:type="[^"]+" r:id="[^"]+"/>', "", document_xml)
        settings_xml = re.sub(r'<w:evenAndOddHeaders(?: w:val="[^"]+")?/>', "", settings_xml)
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                data = document_xml.encode("utf-8")
            elif item.filename == "word/settings.xml":
                data = settings_xml.encode("utf-8")
            dst.writestr(item, data)
    temp_path.replace(path)


def build():
    doc = Document()
    style_document(doc)
    doc.core_properties.title = "Legacy Odoo 17 Manufacturing User Manual"
    doc.core_properties.subject = "Step-by-step operating guide for Legacy Manufacturers Limited"
    doc.core_properties.author = "Legacy Manufacturers Limited"
    doc.core_properties.keywords = "Odoo 17, Manufacturing, Multi-Output, Packaging Recipe, Shop Floor"

    # Editorial cover
    for _ in range(4):
        spacer = doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(14)
    kicker = doc.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kr = kicker.add_run("OPERATIONS HANDBOOK")
    set_run_font(kr, size=11, color=GOLD, bold=True)
    kicker.paragraph_format.space_after = Pt(18)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(9)
    tr = title.add_run("Odoo 17 Manufacturing")
    set_run_font(tr, size=30, color=NAVY, bold=True)
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = subtitle.add_run("Step-by-Step User Manual")
    set_run_font(sr, size=17, color=BLUE, bold=False)
    subtitle.paragraph_format.space_after = Pt(30)

    org = doc.add_paragraph()
    org.alignment = WD_ALIGN_PARAGRAPH.CENTER
    org_run = org.add_run("LEGACY MANUFACTURERS LIMITED")
    set_run_font(org_run, size=12, color=NAVY, bold=True)
    dbp = doc.add_paragraph()
    dbp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    dbr = dbp.add_run("Validated against: odoo17_legacy_masterdata_dev")
    set_run_font(dbr, size=10, color=GRAY, italic=True)
    dbp.paragraph_format.space_after = Pt(50)

    cover_note = doc.add_paragraph()
    cover_note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cnr = cover_note.add_run("Covers master data setup, packaging recipes, custom multi-output manufacturing, reconciliation, work orders, Shop Floor, planning, and reporting.")
    set_run_font(cnr, size=10.5, color=GRAY)
    cover_note.paragraph_format.left_indent = Inches(0.45)
    cover_note.paragraph_format.right_indent = Inches(0.45)
    cover_note.paragraph_format.space_after = Pt(25)
    rev = doc.add_paragraph()
    rev.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = rev.add_run("Version 1.0  |  3 August 2026")
    set_run_font(rr, size=9.5, color=GOLD, bold=True)

    page_break(doc)

    add_page_title(doc, "How to Use This Manual", "Follow the sections in sequence for setup; use the later checklists during daily production.")
    add_callout(doc, "SCOPE", "This guide documents the Manufacturing and Shop Floor interfaces visible in the Legacy development master-data database. It uses the configured TSP production line and packaging recipe as examples. Screen labels may vary slightly by user access rights.")
    doc.add_heading("Contents", level=1)
    contents = [
        ("1", "Access and navigation"),
        ("2", "Manufacturing process at a glance"),
        ("3", "Master-data setup sequence"),
        ("4", "Create and maintain packaging recipes"),
        ("5", "Create a custom multi-output Bill of Materials"),
        ("6", "Create a manufacturing order"),
        ("7", "Plan finished outputs and packaging"),
        ("8", "Confirm and execute production"),
        ("9", "Reconcile output, loss, and packaging"),
        ("10", "Complete, scrap, unbuild, and correct"),
        ("11", "Planning and reporting"),
        ("12", "Daily checklists and troubleshooting"),
    ]
    add_data_table(doc, ["Section", "Topic"], contents, [1250, 8110])
    add_callout(doc, "TEST DATABASE", "The database displays a neutralization banner. Treat it as a test environment; repeat approved steps in production only after validation and authorization.", color=GOLD, fill="FFF8E8")

    page_break(doc)
    add_page_title(doc, "1. Access and Navigation", "Log in to the correct database and open the Manufacturing workspace.")
    add_step(doc, 1, "Open the Odoo database", "Browse to http://localhost:8077/web?db=odoo17_legacy_masterdata_dev.")
    add_step(doc, 2, "Sign in", "Enter your assigned Odoo email or username and password, then select Log in. The administrator account was used only to validate this manual.")
    add_step(doc, 3, "Open Manufacturing", "From the application launcher, select Manufacturing. The landing page is the Work Centers Overview.")
    add_step(doc, 4, "Use the main menus", "Use Operations for Manufacturing Orders and Work Orders; Planning for schedules; Products for products and Bills of Materials; Reporting for analysis; and Configuration for packaging recipes, work centers, and operations.")
    add_screenshot(doc, "02_manufacturing_overview.png", "Figure 1. Manufacturing Work Centers Overview in the Legacy database.", "Odoo Manufacturing overview showing four Legacy production-line work centers: TSP, Instant Thobwa, Instant Porridge, and Corn Puffs.")
    add_callout(doc, "ACCESS NOTE", "If a menu described in this manual is missing, request the appropriate Manufacturing, Inventory, or Shop Floor access group. Do not use the administrator account for routine production work.")

    page_break(doc)
    add_page_title(doc, "2. Manufacturing Process at a Glance", "Legacy custom manufacturing links bulk production, packaged finished goods, and packaging-material reconciliation.")
    flow = [
        ("1", "Maintain master data", "Products, work centers, operations, packaging materials"),
        ("2", "Define packaging recipes", "Finished pack, base quantity, recipe version, material quantities, waste and rounding"),
        ("3", "Build the BoM", "Bulk/WIP product, raw materials, Custom Multi-Output workflow, process type, operations"),
        ("4", "Create the MO", "Select product, quantity, BoM, dates, responsible person, finished-output plan"),
        ("5", "Confirm and execute", "Reserve components, perform work orders, record output and packaging consumption"),
        ("6", "Reconcile and close", "Review usable output, loss, packaged equivalent, balance/variance, lots, and completion"),
    ]
    add_data_table(doc, ["Stage", "Action", "Primary result"], flow, [900, 2450, 6010])
    add_callout(doc, "CONTROL POINT", "Do not confirm an MO until the selected BoM, packaging recipes, output quantities, and scheduled date have been reviewed. Confirmation creates operational demand and work orders.", color=RED, fill="FCEEEE")
    doc.add_heading("Custom workflow choices", level=2)
    add_bullet(doc, "Custom Multi-Output: enables the Legacy output-plan, packaging-consumption, and reconciliation controls.", "Custom Multi-Output:")
    add_bullet(doc, "Integrated Production and Packaging: use when bulk production and final packaging are controlled in one manufacturing order.", "Integrated Production and Packaging:")
    add_bullet(doc, "Multi-Variant Packaging: use when one bulk output is packed into more than one finished-product variant.", "Multi-Variant Packaging:")

    page_break(doc)
    add_page_title(doc, "3. Master Data Setup Sequence", "Create records in dependency order to avoid missing selections and calculation errors.")
    setup_rows = [
        ("1", "Products / Product Variants", "Products > Products", "Create raw materials, WIP/bulk items, packaging items, and finished packaged goods with correct UoM and tracking."),
        ("2", "Work Centers", "Configuration > Work Centers", "Set the production line, capacity, calendar, efficiency, and costing settings."),
        ("3", "Operations", "Configuration > Operations", "Create the production steps and assign each to the correct work center."),
        ("4", "Packaging Recipes", "Configuration > Packaging Recipes", "Define materials and quantities required for each finished package."),
        ("5", "Bills of Materials", "Products > Bills of Materials", "Link raw materials, workflow, process type, and ordered operations."),
    ]
    add_data_table(doc, ["Order", "Record", "Menu path", "What to verify"], setup_rows, [800, 1900, 2180, 4480])
    doc.add_heading("Product-code conventions observed in the database", level=2)
    add_data_table(doc, ["Prefix", "Observed use and example"], [
        ("RM-", "Raw material, for example [RM-SOYA-BEANS]."),
        ("WIP-", "Bulk or work-in-process material, for example [WIP-BULK-TSP]."),
        ("PKG-", "Packaging material, for example [PKG-INNER-PACKAGING-700G]."),
        ("FG-", "Finished packaged product, for example [FG-TSP-CASE-10-X-700G]."),
    ], [1500, 7860])
    add_callout(doc, "UNIT-OF-MEASURE CHECK", "Keep mass, units, and pack conversions consistent. The configured TSP example manufactures 7.00000 kg of bulk TSP and uses a finished case packaging recipe with unit-based packaging materials.", color=GOLD, fill="FFF8E8")

    page_break(doc)
    add_page_title(doc, "4. Create and Maintain Packaging Recipes", "Menu: Manufacturing > Configuration > Packaging Recipes")
    add_step(doc, 1, "Select New", "Create one active recipe for each packaged finished product and recipe version.")
    add_step(doc, 2, "Complete the recipe header", "Enter Name, Code, Product, Base Qty and UoM, Version, Company, Valid From/To, Active, Operation, and Workcenter.")
    add_step(doc, 3, "Add packaging materials", "On Packaging Materials, select Add a line for each item. Enter Packaging Product, Qty Per Base, Product UoM, Wastage Percentage, Rounding Method, Operation, and whether manual adjustment is allowed.")
    add_step(doc, 4, "Add notes and validate", "Use Notes for instructions or assumptions. Confirm that the recipe is active and its validity dates cover the planned production date.")
    add_screenshot(doc, "03_packaging_recipe.png", "Figure 2. Configured TSP case packaging recipe and packaging-material lines.", "Packaging Recipe form for TSP Case 10 by 700 grams, showing header fields and inner and outer packaging material lines.")

    doc.add_heading("Configured example", level=2)
    recipe_rows = [
        ("Recipe", "PR-TSP-CASE-10-X-700G"),
        ("Finished product", "[FG-TSP-CASE-10-X-700G] TSP (Case (10 x 700g))"),
        ("Base", "1.00000 Units, version 1.0"),
        ("Inner packaging", "[PKG-INNER-PACKAGING-700G] - 10.00000 Units"),
        ("Outer packaging", "[PKG-OUTER-PACKAGING-700G] - 1.00000 Units"),
        ("Operation / work center", "Packaging / WC-TSP-01 TSP Production Line"),
    ]
    add_data_table(doc, ["Field", "Configured value"], recipe_rows, [2500, 6860])
    add_callout(doc, "VERSIONING", "When material content or consumption rules change, close the old validity period and create a new version. Avoid overwriting a recipe that has already supported completed production.")

    page_break(doc)
    add_page_title(doc, "5. Create a Custom Multi-Output Bill of Materials", "Menu: Manufacturing > Products > Bills of Materials")
    add_step(doc, 1, "Select New", "Choose the bulk/WIP product and product variant that will be produced before or during packaging.")
    add_step(doc, 2, "Enter quantity and reference", "Set the base manufacturing quantity and UoM. Use a clear reference such as LEGACY-TSP-CASE-10-X-700G.")
    add_step(doc, 3, "Select the workflow", "Set Manufacturing Workflow to Custom Multi-Output. Choose Integrated Production and Packaging or Multi-Variant Packaging as required.")
    add_step(doc, 4, "Set the BoM type", "Use Manufacture this product for production BoMs. Use Kit only when the business process genuinely requires a kit.")
    add_step(doc, 5, "Add components", "On Components, enter the raw materials and quantities required for the BoM base quantity.")
    add_screenshot(doc, "05_custom_bom.png", "Figure 3. TSP custom multi-output BoM header and component setup.", "Bill of Materials form for Bulk TSP showing quantity 7 kilograms, Custom Multi-Output workflow, Integrated Production and Packaging process type, and Soya Beans component.")
    add_callout(doc, "EXAMPLE", "The configured TSP BoM produces 7.00000 kg of [WIP-BULK-TSP] from 7.00000 kg of [RM-SOYA-BEANS]. Verify real yields and losses with the production owner before using a BoM operationally.", color=GOLD, fill="FFF8E8")

    page_break(doc)
    add_page_title(doc, "5.1 Configure BoM Operations", "Operations define the ordered work that appears on Manufacturing Orders and Shop Floor.")
    add_step(doc, 1, "Open the Operations tab", "Select Add a line to create a new operation or Copy Existing Operations to reuse validated operations.")
    add_step(doc, 2, "Assign each operation", "Set the operation name, work center, duration method, duration, and instructions.")
    add_step(doc, 3, "Place operations in production order", "Drag the row handles so the list matches the actual routing. Dependencies determine whether a work order is Ready or Waiting for another WO.")
    add_step(doc, 4, "Review outputs", "Use By-products only for genuine secondary outputs. The Legacy Finished Output Plan is handled on the MO when Custom Multi-Output is selected.")
    add_screenshot(doc, "06_bom_operations.png", "Figure 4. TSP BoM operations assigned to the TSP production line.", "BoM Operations tab listing Soya Bean Cleaning, Milling, Extrusion, Oil Extraction, Cake Milling, Grading, Packaging, Weighing, and Palletizing on WC-TSP-01.")
    add_callout(doc, "DURATION", "The configured example displays manual durations of 00:00. Enter realistic expected durations before relying on capacity planning or OEE analysis.", color=RED, fill="FCEEEE")

    page_break(doc)
    add_page_title(doc, "6. Create a Manufacturing Order", "Menu: Manufacturing > Operations > Manufacturing Orders")
    add_step(doc, 1, "Select New", "The MO opens in Draft status. Do not confirm until all planning fields are complete.")
    add_step(doc, 2, "Select product and quantity", "Choose the bulk/WIP product to manufacture and enter the planned quantity and UoM.")
    add_step(doc, 3, "Select the BoM", "Choose the matching, approved BoM. Confirm that its workflow is Custom Multi-Output and its process type is correct.")
    add_step(doc, 4, "Set schedule and owner", "Enter Scheduled Date and review the calculated End date. Assign the Responsible user.")
    add_step(doc, 5, "Load packaging logic", "Use Reload Packaging Recipes after selecting/changing outputs or recipes. Use Recalculate Outputs after quantity or actual-output changes.")
    add_screenshot(doc, "04_custom_multi_output_mo.png", "Figure 5. New MO with Custom Multi-Output reconciliation controls enabled.", "New Manufacturing Order form with Custom Multi-Output selected, buttons to Reload Packaging Recipes and Recalculate Outputs, and reconciliation fields for usable output, process loss, packaged equivalents, remaining bulk, and variance approval.")
    add_callout(doc, "DO NOT SAVE TEST DATA", "This manual used an unsaved draft only to inspect fields; the draft was discarded. In live use, save and confirm only genuine, authorized production orders.")

    page_break(doc)
    add_page_title(doc, "7. Plan Finished Outputs and Packaging", "Complete the output plan before confirmation so material demand and reconciliation have a reliable baseline.")
    doc.add_heading("Finished Output Plan tab", level=2)
    output_fields = [
        ("Product", "Finished packaged product to receive into stock."),
        ("Output Classification", "Select the classification required by the configured workflow."),
        ("Planned Qty", "Planned number of finished units or packs."),
        ("Actual Qty", "Enter after production; do not use planned quantity as a substitute."),
        ("Net Content Qty / UoM", "Bulk content represented by one finished unit."),
        ("Equivalent Bulk Qty", "Calculated/controlled bulk equivalent of the output."),
        ("Packaging Recipe / Version", "Recipe that determines packaging-material demand."),
        ("Lot", "Finished-output lot or serial reference when tracking is enabled."),
    ]
    add_data_table(doc, ["Field", "How to use it"], output_fields, [2600, 6760])
    doc.add_heading("Packaging Consumption tab", level=2)
    add_bullet(doc, "Review Finished Product, Packaging Product, Qty Per Unit, Planned Output Qty, and Planned Packaging Qty.")
    add_bullet(doc, "After production, review Actual Output Qty, Expected Actual Packaging Qty, and Actual Consumed Qty.")
    add_bullet(doc, "Investigate Variance Qty and Variance Percentage. Enter a specific Variance Reason when consumption differs from expectation.")
    add_bullet(doc, "Confirm the linked Stock Move and Operation are correct before completion.")
    add_callout(doc, "RECALCULATE", "Run Recalculate Outputs whenever output quantities, recipes, or actual quantities change. Then re-check packaging consumption and reconciliation totals.", color=GOLD, fill="FFF8E8")

    page_break(doc)
    add_page_title(doc, "8. Confirm and Execute Production", "Confirmation activates component demand and generates work orders from the BoM routing.")
    add_step(doc, 1, "Review components", "On Components, confirm the products, source locations, quantities to consume, UoMs, and availability. Resolve shortages before starting affected work.")
    add_step(doc, 2, "Select Confirm", "The MO moves from Draft to Confirmed. Work orders become Pending, Waiting, Ready, or In Progress according to availability and dependencies.")
    add_step(doc, 3, "Open Work Orders or Shop Floor", "Use Manufacturing > Operations > Work Orders for a list view, or open the Shop Floor application for operator execution.")
    add_step(doc, 4, "Assign the station and operator", "In Shop Floor, select the relevant Legacy work center and operator. Use All MO or My WO to control the display.")
    add_step(doc, 5, "Run the operation", "Start the ready work order, follow instructions, record consumed quantities and lots, pause when work stops, use Block for a genuine constraint, and select Done when the operation is completed.")
    add_step(doc, 6, "Register production", "Use Register Production for produced quantity and tracked lots. Close Production only after production and quality entries are complete.")
    add_screenshot(doc, "01_shop_floor.png", "Figure 6. Shop Floor station selection for the four Legacy production lines.", "Shop Floor interface showing work-center selection for TSP, Instant Thobwa, Instant Porridge, and Corn Puffs production lines.")
    add_callout(doc, "STATUS GUIDE", "Waiting for components means required material is unavailable; Waiting for another WO means an earlier operation must finish; Ready means the work may start; In Progress means time is being recorded; Finished means the work order is complete.")

    page_break(doc)
    add_page_title(doc, "9. Reconcile Output, Loss, and Packaging", "The MO should explain where planned bulk material went before it is closed.")
    recon_fields = [
        ("Planned Usable Output Qty", "Expected usable bulk output."),
        ("Actual Usable Output Qty", "Measured usable bulk output after processing."),
        ("Planned Process Loss Qty", "Expected production loss."),
        ("Process Loss Qty", "Actual measured production loss."),
        ("Total Planned Packaged Equivalent", "Planned bulk represented by finished-output lines."),
        ("Total Actual Packaged Equivalent", "Actual bulk represented by actual finished output."),
        ("Expected / Remaining Bulk Qty", "Bulk expected to remain and the actual remainder."),
        ("Reconciliation Difference", "Unexplained difference after outputs, losses, and remainder."),
        ("Reconciliation Status", "Balanced when the configured reconciliation equation is satisfied."),
        ("Variance Reason / Approved", "Document and authorize accepted variance according to policy."),
    ]
    add_data_table(doc, ["Control", "Required review"], recon_fields, [3050, 6310])
    doc.add_heading("Recommended close sequence", level=2)
    for item in [
        "Enter actual usable output and actual process loss.",
        "Enter actual finished quantities and lots on Finished Output Plan.",
        "Record actual packaging consumption and variance reasons.",
        "Select Recalculate Outputs.",
        "Confirm packaged equivalents, remaining bulk, and difference.",
        "Resolve the difference or document and obtain variance approval.",
        "Complete remaining work orders and mark the MO Done.",
    ]:
        add_number(doc, item)
    add_callout(doc, "BALANCE RULE", "Do not approve a variance merely to force closure. The approver should be independent of the data entry where practical and should confirm physical quantities, stock moves, and supporting notes.", color=RED, fill="FCEEEE")

    page_break(doc)
    add_page_title(doc, "10. Completion, Scrap, Unbuild, and Corrections", "Use the transaction that matches the physical event and preserve traceability.")
    correction_rows = [
        ("Finish the MO", "MO form", "Use when all components, outputs, work orders, lots, and reconciliation are complete."),
        ("Scrap", "Operations > Scrap", "Use for material or output that is physically lost, damaged, contaminated, or otherwise unusable. Select product, quantity, UoM, source, scrap location, and lot where required."),
        ("Unbuild", "Operations > Unbuild Orders", "Use to reverse a manufactured product into components when the physical operation and accounting treatment require it."),
        ("Cancel", "MO action, subject to state", "Use only for an order that will not be executed. Review reservations and related moves."),
        ("Correct actuals", "MO / stock moves", "Correct before closure where possible. After closure, follow the approved inventory/accounting correction process instead of silently changing history."),
    ]
    add_data_table(doc, ["Action", "Where", "When to use"], correction_rows, [1700, 1900, 5760])
    add_callout(doc, "TRACEABILITY", "Use lot/serial tracking consistently for raw materials, bulk output, and finished products whenever configured. Attach supporting records or log a note when correcting a significant variance.")

    page_break(doc)
    add_page_title(doc, "11. Planning and Reporting", "Use planning to sequence work and reporting to monitor duration, productivity, and equipment effectiveness.")
    planning_rows = [
        ("Planning by Production", "Planning > Planning by Production", "Review and schedule work by manufacturing order."),
        ("Planning by Workcenter", "Planning > Planning by Workcenter", "Balance work across the TSP, Thobwa, Porridge, and Corn Puffs lines."),
        ("Master Production Schedule", "Planning > Master Production Schedule", "Plan demand-driven production when the MPS process is in use."),
        ("Work Orders", "Reporting > Work Orders", "Compare expected and real operation performance."),
        ("Overall Equipment Effectiveness", "Reporting > Overall Equipment Effectiveness", "Review availability, performance, and quality-related equipment effectiveness."),
        ("Production Analysis", "Reporting > Production Analysis", "Analyze manufacturing quantities, timing, products, and other available measures."),
    ]
    add_data_table(doc, ["View", "Menu path", "Purpose"], planning_rows, [2300, 3100, 3960])
    doc.add_heading("Planning discipline", level=2)
    add_checklist_table(doc, [
        "Maintain realistic operation durations and work-center calendars; otherwise capacity and OEE results will be misleading.",
        "Plan by work center when competing orders use the same production line.",
        "Review late, blocked, and waiting work orders daily and assign an owner for each constraint.",
        "Use the same filters and date basis when comparing reports between periods.",
    ])

    page_break(doc)
    add_page_title(doc, "12. Daily Operating Checklists", "Use these checks at handover, before confirmation, and before closure.")
    doc.add_heading("Planner / production supervisor - before confirmation", level=2)
    add_checklist_table(doc, [
        "Correct bulk/WIP product, quantity, UoM, and BoM selected.",
        "Custom Multi-Output and the correct process type selected.",
        "Scheduled date, end date, responsible person, and work center are realistic.",
        "Finished Output Plan matches the approved production plan.",
        "Packaging recipes are active, within validity dates, and at the correct version.",
        "Components and packaging materials are available or have an approved shortage plan.",
        "Reload Packaging Recipes and Recalculate Outputs completed after changes.",
    ])

    doc.add_heading("Operator - during production", level=2)
    add_checklist_table(doc, [
        "Correct station, work order, operator, and product confirmed.",
        "Work started only when status is Ready and safety/quality prerequisites are met.",
        "Actual consumption, quantities, lots, scrap, downtime, and blocks recorded promptly.",
        "Work paused when production stops and marked Done only when the operation is complete.",
    ])

    supervisor_heading = doc.add_heading("Supervisor / approver - before MO completion", level=2)
    add_checklist_table(doc, [
        "All work orders complete and no unexplained block remains.",
        "Actual usable output, process loss, packaged outputs, and lots entered.",
        "Actual packaging consumption recorded and variances explained.",
        "Recalculate Outputs completed; remaining bulk verified physically.",
        "Reconciliation is Balanced, or variance is supported and properly approved.",
        "Stock moves and destination locations are correct before marking Done.",
    ])

    page_break(doc)
    # Consume the final manual break on a zero-height spacer. This avoids a
    # Word repagination defect that can omit the first glyphs of the heading
    # when page-break-before is applied directly to the last heading.
    spacer = doc.add_paragraph()
    spacer.paragraph_format.page_break_before = True
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.line_spacing = Pt(1)
    doc._manual_break_pending = False
    add_page_title(doc, "12.1 Troubleshooting", "Use the symptom to identify the first control to check.")
    troubleshooting = [
        ("Packaging recipe not available", "Recipe inactive, outside validity date, wrong company/product, or wrong version", "Check recipe header, dates, product, company, and Active; then Reload Packaging Recipes."),
        ("Packaging demand is wrong", "Base quantity, Qty Per Base, waste, rounding, output quantity, or recipe version is wrong", "Correct the recipe/output plan and run Recalculate Outputs."),
        ("Work order is waiting", "Component shortage or preceding operation incomplete", "Review status, availability, reservations, and operation sequence."),
        ("Reconciliation is not balanced", "Actual output, loss, remainder, finished quantities, packaging consumption, or UoM conversion is incomplete/wrong", "Verify physical counts and each actual field, then recalculate. Do not approve until the cause is documented."),
        ("Cannot complete MO", "Open work order, missing lot, insufficient consumption/output entry, or unresolved validation", "Read the validation message; complete the relevant tab or work order and retry."),
        ("Planning is unrealistic", "Operation durations, calendars, capacities, or work-center assignments are incomplete", "Correct master data and reschedule; do not treat inaccurate plan output as a production commitment."),
        ("Menu or button is missing", "Insufficient user access or feature configuration", "Ask the system administrator to review access groups and Manufacturing settings."),
    ]
    add_data_table(doc, ["Symptom", "Likely cause", "First action"], troubleshooting, [2000, 3400, 3960])
    add_callout(doc, "ESCALATE", "Escalate repeated calculation differences, unexpected stock moves, access-control failures, or posting errors to the Odoo support/development team with the MO reference, product, date/time, user, screenshots, and exact error message.", color=RED, fill="FCEEEE")

    doc.save(OUTPUT)
    force_shared_odd_even_headers(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
